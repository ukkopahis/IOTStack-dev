#!/usr/bin/python3
"""
Module to load and write docker-compose.yml files based service.yml template
snippets.

Note that the term "service" is used for both docker services and menu.sh
service selection. For clarity this source code internally will use the term:

* "template" for the menu.sh-selections, i.e. .templates-subfolders.
* "service" for the docker service containers, as defined in
  docker-compose.yml. A template may thus contain multiple services.

To be consistent with /docs-documentation and menu.sh terminology, user visible
messages will still only use the term "container".
"""

import argparse
import copy
import logging
import sys
from collections import OrderedDict
from pathlib import Path
from typing import List, Dict, Set, Union, Optional
from collections.abc import Iterator
from ruamel.yaml import YAML
from deps import consts

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
        value with two ':'-characters, it's split at the first occurrence,
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

    def get(self, path: PathType) -> "NestedDictList.LeafValueType":
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
        for item_path, _, parent, parent_key in NestedDictList.__items_converted(self.root):
            # find item to set
            if list(map(str,item_path)) == keys:
                break
        else:
            # pylint false positive warning workaround
            parent, parent_key = None, None # type: ignore
            raise ValueError(f'No path={path} found in {sorted(self)}')
        if isinstance(parent, dict):
            parent[parent_key] = new_value
            return
        assert isinstance(parent_key, int) and isinstance(parent, list)
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
        """Generator of converted *path* and *value* pairs."""
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
        """Converted deep-walk of *root* -> Iterator(tuple(path, value,
        value_parent, parent_key)). Returned iterator lists all leaf values.

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
            Iterator[tuple[__KeyListType,
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
            key_prefix = []
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
    """Represents a docker-compose.yml or a template's service.yml"""
    def __init__(self, service_yml_path: Path):
        self.service_yml_path = service_yml_path
        self.name = str(self)
        self.bare_yml = yaml.load(self.service_yml_path)
        self.yml_view = NestedDictList(self.bare_yml)
        logger.debug('ServiceTemplate(%s) loaded with %i elements (%i roots)',
                     self.name, len(self.yml_view), len(self.bare_yml.keys()))
        #yaml.dump(self.bare_yml, sys.stderr)

    def __str__(self):
        if self.service_yml_path.name == 'service.yml':
            return self.service_yml_path.parent.name
        return self.service_yml_path.name

    def public_ports(self) -> Set[int]:
        """Return set of host ports exposed by this template, that may conflict
        with other services."""
        # TODO: add parseable comment "network_mode: host" service templates
        # port may be "bind_addr:public:private" or "public:private"
        return {port.split(':')[-2]
                for service in self.bare_yml.values()
                for port in service.get('ports', []) }

    def variables(self) -> dict[str, str]:
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
        to their paths. Will raise ValueError if there are unreplaced
        variables left."""
        result = copy.deepcopy(self)
        for path, val in variables.items():
            if path in result.yml_view:
                result.yml_view.set(path, val)
        unreplaced = result.variables()
        if unreplaced:
            raise ValueError(f'Unreplaced variables {unreplaced}')
        return result

class Templates:
    """
    Access and actions to the ".templates" folder content.
    """

    KNOWN_PORT_CONFLICTS = {53,}

    def __init__(self, template_folder_path: Path):
        """All templates, per default loads everyting from .templates"""
        self.templates = Templates.__load_templates(template_folder_path)
        """Currently loaded TemplateFile:s"""
        self.env_template = Templates.__load_env(template_folder_path)
        """Common base TemplateFile, if available."""

    @staticmethod
    def __load_env(template_folder_path: Path) -> Optional[TemplateFile]:
        env_file = template_folder_path / 'env.yml'
        if env_file.exists():
            return TemplateFile(env_file)
        return None

    @staticmethod
    def __load_templates(template_folder_path: Path) \
            -> Dict[str,TemplateFile]:
        """Scan for ServiceTemplate:s from every subfolder of
        template_folder_path to loaded templates"""
        if not template_folder_path.exists():
            raise ValueError(f"Templates directory doesn't exist: "
                             f"{template_folder_path}")
        service_glob = sorted(Path(template_folder_path).glob('*/service.yml'))
        if len(service_glob)==0:
            raise ValueError(f"No templates found in {service_glob}")
        return {service_file.parent.name: TemplateFile(service_file)
                for service_file in service_glob}

    def conflicting_ports(self, verbose=True) -> Dict[int, Set[str]]:
        """Return dict with ports as keys and values as a set of service
        names."""
        service_ports = {name: template.public_ports()
                 for name, template in self.templates.items()}
        port_services = {} # type: Dict[int, Set[str]]
        for service, ports in service_ports.items():
            for port in ports:
                port_set = port_services.setdefault(int(port), set())
                port_set.add(service)
        conflicts = {port: services for port, services in port_services.items()
                     if len(services)>1}
        if verbose:
            for port, services in conflicts.items():
                if int(port) in Templates.KNOWN_PORT_CONFLICTS:
                    logging.info('Services using port %s: %s but users'
                                 ' are meant to pick only one of these',
                                 port, services)
                else:
                    logging.warning(
                        "Services using the SAME CONFLICTING port %s: %s", port,
                        services)
        return conflicts

class Stack:
    """
    High-level operations for a given docker-compose.yml and .templates folder.
    """
    def __init__(self, docker_compose: Path, templates_folder: Path):
        """Load a docker-compose.yml file as the current state with templates
        loaded for services loaded from *templates_folder*"""
        self.current_state = TemplateFile(Path(docker_compose))
        self.templates = Templates(templates_folder)

    def selected_templates(self) -> Set[str]:
        """Return templates selected in the current docker-compose.yml. Some
        templates may include multiple docker-services, but a template is
        considered selected, as long as a there is a service with the same name
        as the template."""
        services = self.current_state.bare_yml['services'].keys()
        templates = self.templates.templates.keys()
        return services & templates

    def add_template(self, template: TemplateFile,
                     append_prefix="service") -> None:
        """Add *template* to the in-memory current_state."""
        add_parent = self.current_state.bare_yml
        if append_prefix:
            if append_prefix in add_parent:
                add_parent = add_parent[append_prefix]
            else:
                add_parent = OrderedDict()
                self.current_state.bare_yml[append_prefix] = add_parent
        # actual add
        # FIXME: password replacements
        # save

    def write_docker_compose(self, backup=True):
        """Write in-memory changes to docker-compose.yml"""
        # TODO

def check_op(args):
    """Check all templates for problems and exit."""
    if args.templates:
        print('ERROR: must not specify any containers for checking',
              file=sys.stderr)
        sys.exit(99)
    templates = Templates(Path(consts.templatesDirectory))
    conflicts = templates.conflicting_ports(verbose=True)
    sys.exit(int(len(conflicts) > 0))

def show_op(stack, args):
    """List all available templates"""
    if 'ALL' in args.templates:
        for template in stack.templates.templates.keys():
            print(template)

def list_op(stack, args):
    """List current templates and their passwords"""
    if args.templates:
        logger.warning('--list ignores CONTAINER_NAME arguments.')
    for template_name in sorted(stack.selected_templates()):
        print(template_name)
        template = stack.templates.templates[template_name]
        for k, v in template.variables().items():
            if not 'Password' in v:
                continue
            if 'services.'+k in stack.current_state.yml_view:
                pw = stack.current_state.yml_view.get("services."+k)
                print(f'- {k}: {pw}')
            else:
                print(f'- {k} is not set')

def add_op(stack, args):
    """Add templates to the stack"""
    for template_name in args.templates:
        template = stack.templates.templates[template_name]
        stack.add_template(template)
    # After all templates are added apply variable replacement, as some vars
    # may reference services from other templates.
    # TODO: variable replacement
    # TODO: write

def init_logger(verbosity: int):
    """Set-up logging. verbosity: 0=ERROR 1=WARN 2=INFO 3=DEBUG"""
    msg_format = '%(levelname)s: %(message)s'
    if verbosity >= 2:
        msg_format = ('[%(filename)s:%(lineno)s/%(funcName)17s]'
                            '%(levelname)s: %(message)s')
    level = 40 - verbosity*10
    logging.basicConfig(format=msg_format, level=level, stream=sys.stderr)

def main():
    """CLI entrypoint."""
    prog_name=None
    if len(sys.argv) >= 3 and sys.argv[1] == '--prog':
        prog_name = sys.argv[2]
    ap = argparse.ArgumentParser(
        prog=prog_name,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''Examples:
    List all available containers:
        %(prog)s --show

    Add pihole and wireguard services:
        %(prog)s --add -p secret_password pihole wireguard

    To update current service definitions after a "git pull":
        %(prog)s --recreate CURRENT''')
    ap.add_argument('--prog', help=argparse.SUPPRESS)
    ap.add_argument('templates', action='store', nargs='*',
                    metavar='CONTAINER_NAME',
                    help='''Containers to list, add, change or remove,
                    depending on the selected operation. Use the special value
                    "CURRENT" to apply operation for all added containers.''')
    ap.add_argument('-v', '--verbose', action='count', default=1,
                    help='''Print extra information to stderr. Use twice for
                    debug information.''')
    ap.add_argument('-n', '--no-backup', dest='backup', action='store_false',
                    help='''Don't create backup before writing changes. Default
                    is to create backup named
                    "docker-compose.yml.`DATETIME`.bak".''')
    ap.add_argument('-a', '--assign', action='append', nargs='+',
                    metavar='KEY=VALUE',
                    help='''Add variable assignment to set when adding or
                    updating containers e.g. "pihole.ports.80/tcp=1080". When
                    updating, variables default to already previous values read
                    from your current stack file (docker-compose.yml). Use
                    "--list --assign help" to list current keys and values''')
    ap.add_argument('-p', '--default-password', dest='password',
                    help='''Use PASSWORD for all containers instead of creating
                    new random passwords. To update already existing containers
                    use the --recreate flag. Note: some containers will store
                    passwords into their own databases, to change such
                    passwords see the container's documentation.''')
    ap_operations = ap.add_argument_group('Operation, use exactly one')
    op = ap_operations.add_mutually_exclusive_group(required=True)
    op.add_argument('-S', '--show',
                    action='store_const', const=show_op, dest='op',
                    help='''List all available containers.''')
    op.add_argument('-L', '--list',
                    action='store_const', const=list_op, dest='op',
                    help='''Print out current containers in the stack and their
                    passwords.''')
    op.add_argument('-A', '--add',
                    action='store_const', const=add_op, dest='op',
                    help='''Add listed container definitions. Will not modify
                    already existing definitions.''')
    op.add_argument('-R', '--recreate', action='store_true',
                    help='''Recreate listed container definitions. Will
                    overwrite any custom modifications you may have made, but
                    preserves previous passwords.''')
    op.add_argument('-U', '--update', action='store_true',
                    help='''Update listed container definitions.
                    Preserves variable assignments, generated passwords and
                    manual customizations. In certain corner-cases this may
                    result in an broken configuration, requiring a "%(prog)s
                    --recreate CONTAINER" to fix such containers and then
                    reapply your changes. This is an expert option: use only
                    when you need to preserve manual modification.''')
    op.add_argument('-D', '--delete', action='store_true',
                    help='Remove listed containers from the stack.')
    op.add_argument('-C', '--check',
                    action='store_const', const=check_op, dest='op',
                    help='''Check all templates for port conflicts and exit.
                    Use during container template development.''')
    args = ap.parse_args()
    init_logger(args.verbose)
    logger.debug("Program arguments: %s", args)
    if args.op:
        stack = Stack(Path('docker-compose.yml'), Path('.templates'))
        args.op(stack, args)
    else:
        logger.error('No operating mode selected')
        ap.print_usage()

if __name__ == '__main__':
    main()
