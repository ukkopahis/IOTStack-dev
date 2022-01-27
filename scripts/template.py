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
from typing import Type, List, Dict, Set, Union
from collections.abc import Iterator
from ruamel.yaml import YAML
from deps.consts import servicesDirectory, templatesDirectory, \
        volumesDirectory, buildCache, envFile, dockerPathOutput, \
        servicesFileName, composeOverrideFile

logger = logging.getLogger(__name__)
yaml = YAML()

class NestedDictList:
    """Operate on nested dict and list structures using a dot-separated key
    string.

    This class is intended to do the "heavy-lifting" to easily access relevant
    parts of the parsed yml. This is done by applying conversions to the key
    strings so that the relevant data is easily modifiable. E.g. in converting
    a port mapping "1080:80": the container-side "80" becomes part of the key
    string, while the host side port "1080" becomes the value. This is because
    modifications only makes sense to the host-side of port-mapping, the
    container-side port of "80" is a constant for a given container.

    Stated formally, the conversion is done as follows: A PATH (=the
    dot-separated string of nested key indices) leading to a final leaf value
    is converted:
      * If it is parsable as "KEY=VALUE" (i.e. has a '=' -character)
      * If the containing list's parent's key is 'ports', 'volumes' or
        'devices', and the leaf value is parsable as "VALUE:KEY". For a leaf
        value with two ':'-characters, it's split at the first occurance,
        unless the parent key is 'ports', which is split at the last.
    Such converted entries have the parsed KEY replacing the list-index in the
    PATH and have their value replaced with parsed VALUE.

    Adding or removing PATHs is not supported. Only PATHs leading to
    leaf-values are valid.
    """
    PathType = Union[str]
    LeafValueType = Union[str, int, float, bool]

    def __init__(self, backing_dict: dict):
        """Construct instance to query and set values into *backing_dict*."""
        self.root = backing_dict

    def get(self, path: PathType) -> LeafValueType:
        """Get value at converted path *path*."""
        for key, val in self.items():
            if key==path:
                return val
        raise KeyError(f'{path} not in {sorted(self)}')

    def set(self,
            path: PathType,
            new_value: LeafValueType) -> None:
        """Set value at converted path *path* to *new_value*."""
        keys = path.split('.')
        for itemPath, _, parent, parent_key in NestedDictList.__items_converted(self.root):
            # find item to edit
            if list(map(str,itemPath)) == keys:
                break
        else:
            raise ValueError(f'No path={path} found in {sorted(self)}')
        if isinstance(parent, dict):
            parent[parent_key] = new_value
            return
        assert isinstance(parent_key, int)
        element = parent[parent_key]
        # convert lists in ports and volumes from indices to maps
        if isinstance(element, str) and len(keys)>2 and keys[-2] == 'ports':
            _, key = element.rsplit(':', maxsplit=1)
            parent[parent_key] = str(new_value) + ':' + key
        elif isinstance(element, str) and len(keys)>2 \
                and keys[-2] in ( 'volumes', 'devices'):
            if element.count(':'):
                _, key = element.split(':', maxsplit=1)
                parent[parent_key] = str(new_value) + ':' + key
            else:
                parent[parent_key] = str(new_value) + ':' + keys[-1]
        # resolve environment key=value pairs
        elif isinstance(element, str) and '=' in element:
            key, _ = element.split('=', maxsplit=1)
            parent[parent_key] = key + '=' + str(new_value)
        else:
            parent[parent_key] = new_value
        return

    def items(self) -> Iterator[tuple[str, LeafValueType]]:
        for path, val, _, _ in NestedDictList.__items_converted(self.root):
            yield ('.'.join(map(str,path)), val)

    def __str__(self):
        return sorted(self.items())

    def __len__(self):
        return len(list(self.items()))

    def __iter__(self):
        for key, _ in self.items():
            yield key

    __RootType = Union[dict,list,LeafValueType]
    __KeyType = Union[str,int] # str for dict key or int for list index
    __KeyListType = List[__KeyType] # Path before joining to '.'-separated

    @staticmethod
    def __items_converted(root: __RootType) -> \
            Iterator[tuple[__KeyListType,
                           LeafValueType,
                           Union[dict,list],
                           __KeyType]]:
        """Converted deep-walk of *root* -> iterable(tuple(path, value,
        value_parent, parent_key)).

        As *path*s and *value*s are converted, the original key is provided as
        *parent_key*. This can be used to modify the value in the backing
        dict or list: *value_parent*"""
        for path, val, parent in NestedDictList.__items(root):
            if isinstance(parent, dict):
                yield (path, val, parent, path[-1])
            # convert lists in ports, volumes and devices from indices to maps
            elif isinstance(val, str) and len(path)>2 and path[-2] == 'ports':
                value, key = val.rsplit(':', maxsplit=1)
                yield (path[:-1] + [key], value, parent, path[-1])
            elif isinstance(val, str) and len(path)>2 and path[-2] in (
                'volumes', 'devices'):
                if val.count(':'):
                    value, key = val.split(':', maxsplit=1)
                    yield (path[:-1] + [key], value, parent, path[-1])
                else:
                    # docker "undocumented feature" key and value assumed the same
                    yield (path[:-1] + [val], val, parent, path[-1])
            # resolve environment key=value pairs
            elif isinstance(val, str) and '=' in val and len(path)>0:
                key, value = val.split('=', maxsplit=1)
                yield (path[:-1] + [key], value, parent, path[-1])
            else:
                yield (path, val, parent, path[-1])


    @staticmethod
    def __items(root: __RootType,
                key_prefix: __KeyListType = None,
                parent_collection: Union[dict,list] = None) -> \
            Iterator[ tuple[__KeyListType,
                            LeafValueType,
                            Union[dict,list]]]:
        """Deep-walk into nested dicts and lists of *root* ->
        iterable(tuple(path, value, value_parent)) for all the leaf values in
        the structure. Parameter *key_prefix* is the keys that have been needed
        to reach the current recursion level.

        Returned *path* is the list of dict keys or list indices to traverse
        the nested structure of *root* to the the leaf *value*. *value_parent*
        is the dict or list that contained the leaf *value*.
        """
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
        if not parent_collection:
            raise ValueError(f'{root} with key_prefix={key_prefix}'
                             f' must not have empty parent_collection')
        yield (key_prefix, root, parent_collection)

class TemplateFile:
    """Represents a docker-compose.yml or a template service.yml"""
    def __init__(self, service_template_yml: Path):
        self.template_path = service_template_yml
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
        # TODO: add parseable comment "network_mode: host" service templates
        # port may be "bind_addr:public:private" or "public:private"
        return {port.split(':')[-2]
                for service in self.bare_yml.values()
                for port in service.get('ports', []) }

    def variable_items(self) -> dict[str, str]:
        """Return paths to dynamic variables defined in the template. These are
        the variable keys to use in a with_variables() call to replace them.

        Variables are yaml leaf entries containing a variable as the value,
        e.g. %foobar%. Paths are the dot-separated yaml dictionary keys or list
        elements indices leading to such entries. Certain list elements are
        converted from their list&index to better reflect their semantic
        functions in docker-compose. This conversion is done as documented in
        the NestedDictList-class."""
        return {path: value
            for path, value in self.yml_view.items()
            if isinstance(value, str) and value.count('%') >= 2}

    def with_variables(self, variables: Dict[str, str]) -> 'TemplateFile':
        """Return deep copy of the template replacing all variables according
        to their paths.  Will raise ValueError if there are unreplaced
        variables left."""
        result = copy.deepcopy(self)
        for path, val in variables.items():
            if path in result.yml_view:
                result.yml_view.set(path, val)
        unreplaced = result.variable_items()
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
                 for name, template in self.templates.items()}
        conflicts = dict() # type: Dict[Set[int], Set[str]]
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
    from argparse import RawDescriptionHelpFormatter
    ap = argparse.ArgumentParser( formatter_class=RawDescriptionHelpFormatter,
        epilog=f'''Examples:

    Update stack definitions after "git pull":
        {os.path.basename(sys.argv[0])} -r current

    Add pihole and wireguard services:
        {os.path.basename(sys.argv[0])} -p secret_password pihole wireguard
                                 ''')
    ap.add_argument('service', action='append', nargs='*',
                    metavar='SERVICE_NAME',
                    help='''Service to add or update to the stack. Unlisted
                    services are kept unmodified. Use the special value
                    "current" for all services currently in the stack.''')
    ap.add_argument('-v', '--verbose', action='store_true',
                    help="print extra debugging information to stderr")
    ap.add_argument('-C', '--check', action='store_true',
                    help='check all templates for port conflicts and exit')
    ap.add_argument('-N', '--no-backup', action='store_true',
                    help='''Don't create stack backup before making changes.
                    Default is to create backup named
                    "docker-compose.yml.`DATETIME`.bak".''')
    ap.add_argument('-r', '--recreate', action='store_true',
                    help='''Recreate listed service definitions. Will overwrite
                    any custom modifications you may have made, but preserves
                    previous variable assignments and generated passwords.
                    Required to update service definition to their newest
                    IOTstack versions after a "git pull".''')
    ap.add_argument('-a', '--assign', action='append', nargs='+',
                    metavar='ASSIGNMENT',
                    help='''Add variable assignment to set when adding or
                    updating services e.g. "pihole.ports.80/tcp=1080".
                    When updating, variables default to already previous values
                    read from your current stack file (docker-compose.yml).''')
    ap.add_argument('-p', '--default-password', dest='password',
                    help='''Use PASSWORD for all services instead of creating
                    new random passwords. To update already existing services
                    use the --recreate flag . Note: some containers will store
                    passwords into ./volumes, to change such passwords see the
                    container's documentation.''')
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
