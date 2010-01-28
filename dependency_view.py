#!/usr/bin/env python
# 
# LSST Package Dependency Viewer (F. Pierfederici <fpierfed@gmail.com>)
# 
# Given a package name from the current packages list, create a dependency graph
# of that package in Graphviz DOT format. The graph is then printed to STDOUT 
# and can be fed to Graphviz or compatible applications for visualization.
# 
# Usage:
#   dependency_view.py <pkg_name>
# 
# Example:
#   dependency_view.py afw | graphviz
# 

# Imports
import os
import urllib2



# Constants
URL_ROOT = 'http://dev.lsstcorp.org/dmspkgs'
CURRENT_LIST_NAME = 'current.list'
EL_TEMPLATE = '  "%s" [label = "{<head> %s | <end>}"\n     shape = "record"];\n'



class Package(object):
    def __init__(self, 
                 name, 
                 version, 
                 parents=[],
                 arch='generic', 
                 dir_name=None, 
                 base_url=URL_ROOT):
        self.name = name
        self.version = version
        self.architecture = arch
        self.dir_name = dir_name
        self.base_url = base_url
        self.parents = parents
        
        # Build the full package URL.
        self.url = base_url
        if(dir_name):
            self.url += '/' + dir_name
        self.url += '/' + name + '/' + version
        if(arch != 'generic'):
            self.url += '/' + arch
        return



def fetch_url(url):
    """
    Fetch the file pointed to by `url` ands returning its raw content.
    
    
    @param url: the URL-ESCAPED URL or the file to fetch.
    @return content of the file pointed to by URL.
    @throw URLError on errors.
    """
    # Well, timeouts are only supported in Python 2.6 or later...
    f = urllib2.urlopen(url)
    data = f.readlines()
    f.close()
    return(data)


def parse_package_list(raw_data, verbose=False):
    """
    Parse the list of current LSST package and return a dict of the form
    
        {pkg_name: (pkg_architecture, pkg_version, parent_directory)}
    
    parent_directory is either the empty string or 'external' for external
    packages that live under URL_ROOT + '/external'
    
    Package list columns are space separated, '#' at the beginning of a line are
    used for comments. Lists usually start with a title string beginning with 
    
        'EUPS distribution'
        
    which should be skipped when parsing.
    
    @param raw_data: outout of readlines() on the raw package list file.
    @return parsed package list.
    """
    if(raw_data[0].startswith('EUPS distribution')):
        raw_data.pop(0)
    
    packages = {}
    for line in raw_data:
        if(line.startswith('#')):
            continue
        
        # tokens = [pkg_name, pkg_architecture, pkg_version, 'external'] or
        # tokens = [pkg_name, pkg_architecture, pkg_version]
        tokens = line.split()
        num_tokens = len(tokens)
        if(num_tokens == 4):
            pass
        elif(num_tokens == 3):
            tokens.append('')
            num_tokens += 1
        else:
            if(verbose):
                print('Skipped malformed line: "%s"' % (line.strip()))
            continue
        
        # There should be no repetition!
        packages[tokens[0]] = tuple(tokens[1:])
    return(packages)


def parse_dependency_list(raw_data, verbose=False):
    """
    Given a list of dependency rules, line by line (e.g. from readlines() on the
    raw dependency file), parse it and return a list of package names that make
    up the dependency.
    
    Dependency rules have the form
        
        >merge pkg=pkg_name
        ...
        >self
    """
    parents = []
    for line in raw_data:
        if(not line.startswith('>merge')):
            continue
        
        pkg_name = line.strip().split('>merge pkg=', 1)[-1]
        pkg_name = pkg_name.split()[0]
        if(pkg_name):
            parents.append(pkg_name)
    return(parents)


def build_package(pkg_name, pkg_list):
    return(Package(name=pkg_name, 
                   arch=pkg_list[pkg_name][0],
                   version=pkg_list[pkg_name][1],
                   dir_name=pkg_list[pkg_name][2]))


def build_dependency_tree(pkg, pkg_list, pkgs_in_tree=[]):
    """
    Given a package name `pkg_name` and a package list `packages` in the form of
    the dictionary returned by parse_package_list, recurively build the whole
    dependency tree.
    
    Keep track of the packages we have already processed in pkgs_in_tree.
    
    @param pkg: Package instance
    @param pkg_list: list specifying the known package names, versions etc.
    @param pkgs_in_tree: list of Package instances that have been processed.
    @return: None. The `pkg` object is modified in place.
    """
    # Fetch the dependency list of pkg_name.
    url = pkg.url + '/the.manifest'
    pkg.parents = [build_package(pt, pkg_list) \
                   for pt in parse_dependency_list(fetch_url(url))]
    
    if(pkg not in pkgs_in_tree):
        pkgs_in_tree.append(pkg.name)
    
    # And now, for each parent, do the same.
    for parent in pkg.parents:
        if(parent.name in pkgs_in_tree):
            continue
        
        build_dependency_tree(parent, pkg_list, pkgs_in_tree)
    return


def plot_dependency_tree(pkg, title='Created by dependency_view.py'):
    """
    Create and return the Graphviz plot in DOT file format.
    
    @param pkg: Package instance for which we want to create the graph.
    @param title: title of the plot.
    @return plot: the plot in DOT format.
    """
    plot = ''
    
    # Header
    plot += 'digraph "%s" {\n' %(title)
    plot += ' graph [rankdir = "BT"];\n'
    
    # Print pkg.
    plot += EL_TEMPLATE %(pkg.name, pkg.name)
    
    # Print the parents recursively.
    plot += _plot_parents(pkg)
    
    # Footer
    plot += '}\n'
    return(plot)
    

def _plot_parents(child):
    subplot = ''
    
    for parent in child.parents:
        subplot += EL_TEMPLATE %(parent.name, parent.name)
        subplot += '  "%s":head -> "%s":end [id = 0];\n' \
                   %(child.name, parent.name)
    
    # Recurse.
    for parent in child.parents:
        # Plot all the sub-children.
        subplot += _plot_parents(parent)
    return(subplot)






if(__name__ == '__main__'):
    import sys
    
    
    try:
        pkg_name = sys.argv[1]
    except:
        print('Usage: dependency_view.py <pkg_name>')
        sys.exit(1)
    
    # Fetch the LSST current.list file.
    # pkg_list = {pkg_name: (pkg_architecture, pkg_version, parent_directory)}
    url = URL_ROOT + '/' + CURRENT_LIST_NAME
    pkg_list = parse_package_list(fetch_url(url))
    
    # Make sure that pkg_name is something we know about!
    if(pkg_name not in pkg_list.keys()):
        print('Error: "%s" is not in %s.' % (pkg_name, url))
        sys.exit(2)
    
    # Create a Package instance with empty dependency list.
    root = build_package(pkg_name, pkg_list)
    
    # Now build the tree.
    build_dependency_tree(root, pkg_list)
    
    # Plot!
    plot = plot_dependency_tree(root, 'Dependencies for %s' % (root.name))
    print(plot)
    
    



































