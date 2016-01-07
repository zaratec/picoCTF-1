"""
Common utilities for the shell manager.
"""

from os import listdir, unlink, sep
from os.path import join, isdir, isfile

import shutil, logging
import json
import re, string
from shutil import copytree, copy2

from voluptuous import Schema
from voluptuous import Required, All, Length, Range
from voluptuous import MultipleInvalid

logger = logging.getLogger(__name__)

# the root of the hacksports local store
HACKSPORTS_ROOT = "/opt/hacksports/"
PROBLEM_ROOT = join(HACKSPORTS_ROOT, "sources")
EXTRA_ROOT = join(HACKSPORTS_ROOT, "extra")
STAGING_ROOT = join(HACKSPORTS_ROOT, "staging")
DEPLOYED_ROOT = join(HACKSPORTS_ROOT, "deployed")
BUNDLE_ROOT = join(HACKSPORTS_ROOT, "bundles")

problem_schema = Schema({
    Required("author"): All(str, Length(min=1, max=32)),
    Required("score"): All(int, Range(min=0)),
    Required("name"): All(str, Length(min=1, max=32)),
    Required("description"): str,
    Required("category"): All(str, Length(min=1, max=32)),
    Required("hints"): list,
    "version": All(str, Length(min=1, max=8)),
    "tags": list,
    "organization": All(str, Length(min=1, max=32)),
    "pkg_description": All(str, Length(min=1, max=256)),
    "pkg_name": All(str, Length(min=1, max=32)),
    "pkg_dependencies": list,
    "pip_requirements": list
})

bundle_schema = Schema({
    Required("author"): All(str, Length(min=1, max=32)),
    Required("problems"): list,
    Required("name"): All(str, Length(min=1, max=32)),
    Required("description"): str,
    Required("categories"): list,
    "version": All(str, Length(min=1, max=8)),
    "tags": list,
    "organization": All(str, Length(min=1, max=32)),
    "dependencies": dict,
    "pkg_dependencies": list
})

config_schema = Schema({
    Required("deploy_secret") : str,
    Required("hostname"): str,
    Required("web_server"): str,
    Required("default_user"): str,
    Required("web_root"): str,
    Required("problem_directory_root"): str,
    Required("obfuscate_problem_directories"): bool,
    Required("banned_ports"): list
}, extra=True)

port_range_schema = Schema({
    Required("start"): All(int, Range(min=0, max=66635)),
    Required("end"): All(int, Range(min=0, max=66635))
})

class FatalException(Exception):
    pass

def get_attributes(obj):
    """
    Returns all attributes of an object, excluding those that start with
    an underscore

    Args:
        obj: the object

    Returns:
        A dictionary of attributes
    """

    return {key:getattr(obj, key) if not key.startswith("_") else None for key in dir(obj)}

def sanitize_name(name):
    """
    Sanitize a given name such that it conforms to unix policy.

    Args:
        name: the name to sanitize.

    Returns:
        The sanitized form of name.
    """

    if len(name) == 0:
        raise Exception("Can not sanitize an empty field.")

    sanitized_name = re.sub(r"[^a-z0-9\+-]", "-", name.lower())

    if sanitized_name[0] in string.digits:
        sanitized_name = "p" + sanitized_name

    return sanitized_name

#I will never understand why the shutil functions act
#the way they do...

def full_copy(source, destination, ignore=[]):
    for f in listdir(source):
        if f in ignore:
            continue
        source_item = join(source, f)
        destination_item = join(destination, f)

        if isdir(source_item):
            if not isdir(destination_item):
                copytree(source_item, destination_item)
        else:
            copy2(source_item, destination_item)

def move(source, destination, clobber=True):
    if sep in source:
        file_name = source.split(sep)[-1]
    else:
        file_name = source

    new_path = join(destination, file_name)
    if clobber and isfile(new_path):
        unlink(new_path)

    shutil.move(source, destination)


def get_problem_root(problem_name, absolute=False):
    """
    Installation location for a given problem.

    Args:
        problem_name: the problem name.
        absolute: should return an absolute path.

    Returns:
        The tentative installation location.
    """

    problem_root = join(PROBLEM_ROOT, sanitize_name(problem_name))

    assert problem_root.startswith(sep)
    if absolute:
        return problem_root

    return problem_root[len(sep):]

def get_problem(problem_path):
    """
    Retrieve a problem spec from a given problem directory.

    Args:
        problem_path: path to the root of the problem directory.

    Returns:
        A problem object.
    """

    json_path = join(problem_path, "problem.json")
    problem = json.loads(open(json_path, "r").read())

    try:
        problem_schema(problem)
    except MultipleInvalid as e:
        logger.critical("Error validating problem object at '%s'!", json_path)
        logger.critical(e)
        raise FatalException

    return problem

def get_bundle_root(bundle_name, absolute=False):
    """
    Installation location for a given bundle.

    Args:
        bundle_name: the bundle name.
        absolute: should return an absolute path.

    Returns:
        The tentative installation location.
    """

    bundle_root = join(BUNDLE_ROOT, sanitize_name(bundle_name))

    assert bundle_root.startswith(sep)
    if absolute:
        return bundle_root

    return bundle_root[len(sep):]

def get_bundle(bundle_path):
    """
    Retrieve a bundle spec from a given bundle directory.

    Args:
        bundle_path: path to the root of the bundle directory.

    Returns:
        A bundle object.
    """

    json_path = join(bundle_path, "bundle.json")

    bundle = json.loads(open(json_path, "r").read())

    try:
        bundle_schema(bundle)
    except MultipleInvalid as e:
        logger.critical("Error validating bundle object at '%s'!", json_path)
        logger.critical(e)
        raise FatalException

    return bundle

def get_config(path):
    """
    Retrieve a configuration object from the given path

    Args:
        path: the full path to the json file

    Returns:
        A python object containing the fields within
    """

    with open(path) as f:
        config_object = json.loads(f.read())

    try:
        config_schema(config_object)
    except MultipleInvalid as e:
        logger.critical("Error validating config file at '%s'!", path)
        logger.critical(e)
        raise FatalException

    for port_range in config_object["banned_ports"]:
        try:
            port_range_schema(port_range)
            assert port_range["start"] <= port_range["end"]
        except MultipleInvalid as e:
            logger.critical("Error validating port range in config file at '%s'!", path)
            logger.critical(e)
            raise FatalException
        except AssertionError as e:
            logger.critical("Invalid port range: (%d -> %d)", port_range["start"], port_range["end"])
            raise FatalException

    config = object()
    for key, value in config_object.items():
        config.__setattr__(key, value)

    return config
