#!/usr/bin/python3
"""
Module to load and write docker-compose.yml files or service.yml snippets.
Methods to find variables and easily allows writing values into them.
"""

import argparse
import copy
import logging
import os
import sys
from pathlib import Path
from typing import List, Dict, Set, Union
from collections.abc import Iterable
from ruamel.yaml import YAML
from deps.consts import (
    servicesDirectory, templatesDirectory, volumesDirectory, buildCache,
    envFile, dockerPathOutput, servicesFileName, composeOverrideFile)

logger = logging.getLogger(__name__)
yaml = YAML()

class NestedDictList:
    """Operate on nested dict and list structures using dot-separated key
    strings.

    Paths leading to list elements are converted from their list-indices:
    * If a list element is "KEY=VALUE" (i.e. has the '=' -character), such
      entries also have the KEY as part of the path.
    * If a list parent key is 'ports' or 'volumes', elements such a list are
      parsed as "VALUE:KEY".
    """

    def __init__(self, backing_dict: dict = None):
        """Construct instance to query and set values into *backing_dict*."""
        self.root = backing_dict

    def get(self, path: str) -> Union[str, int, float]:
        """Get value at converted path *path*."""
        for key, val in self.items():
            if key==path:
                return val
        raise KeyError(f'{path} not in {set(self)}')

    def set(self,
            path: str,
            new_value: Union[str,int,float]) -> None:
        """Set value at converted path *path* to *new_value*."""
        path = path.split('.')
        for itemPath, _, parent, parent_key in NestedDictList.__items_converted(self.root):
            # find item to edit
            if list(map(str,itemPath)) != path:
                continue
            element = parent[parent_key]
            # convert lists in ports and volumes from indices to maps
            if isinstance(element, str) and len(path)>2 and path[-2] == 'ports':
                _, key = element.rsplit(':', maxsplit=1)
                parent[parent_key] = new_value + ':' + key
            elif isinstance(element, str) and len(path)>2 and path[-2] == 'volumes':
                _, key = element.split(':', maxsplit=1)
                parent[parent_key] = new_value + ':' + key
            # resolve environment key=value pairs
            elif isinstance(element, str) and '=' in element and len(path)>0:
                key, _ = element.split('=', maxsplit=1)
                parent[parent_key] = key + '=' +new_value
            else:
                parent[parent_key] = new_value
            return
        raise ValueError(f'No key={path} found in {list(self.items())}')

    def items(self):
        for path, val, _, _ in NestedDictList.__items_converted(self.root):
            yield ('.'.join(map(str,path)), val)

    def __len__(self):
        return len(list(self.items()))

    def __iter__(self):
        for key, _ in self.items():
            yield key

    RootType = Union[dict,set,str,int,float]
    KeyType = Union[str,int] # dict key or list index
    PathType = List[KeyType] # nested keys

    @staticmethod
    def __items_converted(root: RootType) -> \
            Iterable[tuple[PathType,
                           Union[str,int,float],
                           Union[dict,list],
                           KeyType]]:
        """Converted deep-walk of *root* -> iterable(tuple(path, value,
        value_parent, parent_key)).

        As *path*s and *value*s are converted, the original key is provided as
        *parent_key*. This can be used to modify the value in *value_parent*"""
        for path, val, parent in NestedDictList.__items(root):
            # convert lists in ports and volumes from indices to maps
            if isinstance(val, str) and len(path)>2 and path[-2] == 'ports':
                value, key = val.rsplit(':', maxsplit=1)
                yield (path[:-1] + [key], value, parent, path[-1])
            elif isinstance(val, str) and len(path)>2 and path[-2] == 'volumes':
                value, key = val.split(':', maxsplit=1)
                yield (path[:-1] + [key], value, parent, path[-1])
            # resolve environment key=value pairs
            elif isinstance(val, str) and '=' in val and len(path)>0:
                key, value = val.split('=', maxsplit=1)
                yield (path[:-1] + [key], value, parent, path[-1])
            else:
                yield (path, val, parent, path[-1])


    @staticmethod
    def __items(root: RootType,
                key_prefix: PathType = None,
                parent_collection: Union[dict,list] = None) -> \
            Iterable[ tuple[List[Union[str,int]],
                            Union[str,int,float],
                            Union[dict,list]]]:
        """Deep-walk into nested dicts and lists of *root* ->
        iterable(tuple(path, value, value_parent)) for all the leaf values in
        the structure. Parameter *key_prefix* is the keys that have been needed
        to reach the current recursion level.

        Returned *path* is the list of dict keys or list indices to traverse
        the nested structure of *root* to the the leaf *value*. *value_parent*
        is the dict or list that contained the leaf *value*.
        """
        #print('**',collection,max_depth,key_prefix)
        if not key_prefix:
            key_prefix = list()
        if isinstance(root, dict):
            for key, val in root.items():
                yield from NestedDictList.__items(val, key_prefix+[key], root)
            return
        if isinstance(root, list):
            for index, val in enumerate(root):
                yield from NestedDictList.__items(val, key_prefix+[index], root)
            return
        if not root or not isinstance(root, (str, int, float)):
            raise TypeError(f'{type(root)} is an invalid leaf type'
                            f'({root}, key_prefix={key_prefix})')
        yield (key_prefix, root, parent_collection)

class TemplateFile:
    def __init__(self, service_template_yml: str):
        self.template_path = Path(service_template_yml)
        self.name = str(self)
        self.bare_yml = yaml.load(self.template_path)
        self.yml_view = NestedDictList(self.bare_yml)
        logger.debug(f'ServiceTemplate({self.name}) loaded with'
                     f' {len(self.yml_view)} elements'
                     f' from {len(self.bare_yml.keys())} root')
        #yaml.dump(self.bare_yml, sys.stderr)

    def __str__(self):
        if self.template_path.name == 'service.yml':
            return self.template_path.parent.name
        return self.template_path.name

    def public_ports(self) -> Set[int]:
        """Return set of host ports exposed by this template, that may conflict
        with other services."""
        # TODO: add comment to parse for ports when "network_mode: host"
        # port may be "bind_addr:public:private" or "public:private"
        return {port.split(':')[-2]
                for service in self.bare_yml.values()
                for port in service.get('ports', []) }

    def get_variable_items(self) -> dict[str, str]:
        """Return paths to dynamic variables defined in the template. These are
        the variable keys used for with_variables() calls to replace them.

        Variables are yaml leaf entries containing a variable as the value,
        e.g.  %foobar%. Paths are the dot-separated yaml dictionary keys or
        list elements indices leading to such entries. Certain list elements
        are converted from their list&index to better reflect their semantic
        functions in docker-compose. This conversion is done as documented in
        the NestedDictList-class."""
        return {path: value
            for path, value in self.yml_view.items()
            if isinstance(value, str) and len(value.split('%')) >= 2}

    def with_variables(self, variables: Dict[str, str]) -> 'TemplateFile':
        """Return deep copy of the template replacing all variables according
        to their paths.  Will raise ValueError if there are unreplaced
        variables left."""
        result = copy.deepcopy(self)
        for path, val in variables.items():
            if path in result.yml_view:
                result.yml_view.set(path, val)
        unreplaced = result.get_variable_items()
        if unreplaced:
            raise ValueError(f'Unreplaced variables {unreplaced}')
        return result

class Services:

    KNOWN_PORT_CONFLICTS = {53,}

    def __init__(self, template_root=templatesDirectory):
        """All templates, per default loads everyting from .templates"""
        self.templates = {}
        self.common = set()
        if template_root:
            self.__load_templates(template_root)
        envFile = Path(template_root)/'env.yml'
        if envFile.exists():
            self.common.add(TemplateFile(envFile))

    def get_templates(self):
        """Currently loaded ServiceTemplate:s"""
        return self.templates

    def __load_templates(self, templatesDirectory: str):
        """Append ServiceTemplate:s from every subfolder of templatesDirectory
        to loaded templates"""
        if not Path(templatesDirectory).exists():
            raise ValueError(f"Templates directory doesn't exist: {templatesDirectory}")
        serviceGlob = sorted(Path(templatesDirectory).glob('*/service.yml'))
        if len(serviceGlob)==0:
            raise ValueError(f"No templates found in {templatesDirectory}")
        self.templates |= {service_file.parent.name: TemplateFile(service_file)
                for service_file in serviceGlob}
        logger.debug(f'Loaded {len(serviceGlob)} services templates')

    def conflicting_ports(self, verbose=True) -> Dict[Set[int], Set[str]]:
        """Return dict with ports as keys and values as a set of service
        names."""
        ports = {name: template.public_ports()
                 for name,template in self.templates.items()}
        conflicts = dict()
        for service, ports in ports.items():
            for port in ports:
                port_set = conflicts.setdefault(port, set())
                port_set.add(service)
        conflicts = {port: services for port, services in conflicts.items()
                     if len(services)>1}
        for port, services in conflicts.items():
            if int(port) in Services.KNOWN_PORT_CONFLICTS:
                logging.info('Services using port %s: %s'
                             ' but users are meant to pick only one of these',
                             port, services)
            else:
                logging.warning(
                    "Services using the SAME CONFLICTING port %s: %s", port,
                    services)
        return conflicts

def init_logging(verbose=False):
    params = {'format': '%(levelname)s: %(message)s'}
    if verbose:
        params['level'] = logging.DEBUG
        params['format'] = ('[%(filename)s:%(lineno)s/%(funcName)17s]'
                            '%(levelname)s: %(message)s')
    logging.basicConfig(stream=sys.stderr, **params)

class __SplitArgs(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, self.dest, values.split(','))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('-v', '--verbose', action='store_true',
                    help="print extra debugging information")
    ap.add_argument('-c', '--check', action='store_true',
                    help='check templates for port conflicts and exit')
    ap.add_argument('-s', '--service', action='append', dest='services',
                    metavar='SERVICE_NAME',
                    help='''Add or update a service to the stack. May be given
                    multiple times. To overwrite any custom modifications use
                    the --recreate flag.''')
    ap.add_argument('-p', '--variable', action='append',
                    help='''Add variable to set when adding or updating
                    services e.g. pihole.password=mysecret ''')
    ap.add_argument('-r', '--recreate', action='store_true',
                    help='Recreate service definitons')
    args = ap.parse_args()
    init_logging(args.verbose)
    logger.debug("Program arguments: %s", args)
    if args.check:
        if args.services:
            print('ERROR: must not specify any services for checking',
                  file=sys.stderr)
            sys.exit(1)
        Services().conflicting_ports(verbose=True)
        return

if __name__ == '__main__':
    main()
    tc = Services()
    print(tc.conflicting_ports(verbose=True))
    #e = ServiceTemplate(Path(templatesDirectory) / 'env.yml')
