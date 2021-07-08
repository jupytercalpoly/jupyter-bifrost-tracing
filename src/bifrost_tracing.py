"""Main module."""
from IPython import get_ipython
from IPython.core.magic import (Magics, magics_class, cell_magic, line_magic)
from IPython.core.extensions import ExtensionManager
import ast


    

# keep it here for reactive cells later??
@magics_class
class BifrostTracing(Magics):

    @line_magic
    def line_tracing(self, line):
        return line

    @cell_magic
    def tracing(self, line, cell):
        return line, cell


class BifrostWatcher(object):
    def __init__(self, ip):
        self.shell = ip
        self.last_x = None
        self.bifrost_table = {}

    def post_run_cell(self, result):
        ast_tree = ast.parse(result.info.raw_cell)
        assignVisitor = AssignVisitor()
        assignVisitor.visit(ast_tree)
        
        for new_df in assignVisitor.new_dfs:
            columns = get_ipython().run_cell(new_df + '.columns').result
            print(columns)
            if new_df in self.bifrost_table:
                columns_set = set(columns)
                table_set = set(self.bifrost_table[new_df].keys())
                for new_col in (columns_set - table_set):
                    self.bifrost_table[new_df][new_col] = 0
            else:
                self.bifrost_table[new_df] = {col: 0 for col in columns}    


class AttributeVisitor(ast.NodeVisitor):    
    def visit_Attribute(self, node):
        self.attributes = []
        self.attributes.append(node.value.id + "." + node.attr)


class NameVisitor(ast.NodeVisitor):
    def visit_Name(self, node):
        self.names = []
        self.names.append(node.id)


class AssignVisitor(ast.NodeVisitor):
    def __init__(self):
        self.new_dfs = []

    def visit_Module(self, node):
        self.generic_visit(node)
        
    def visit_Assign(self, node):
        nameVisitor = NameVisitor()
        for target in node.targets:
            nameVisitor.visit(target)
        names = nameVisitor.names
        attributeVisitor = AttributeVisitor()
        attributeVisitor.visit(node.value) 
        attributes = attributeVisitor.attributes
        df_mask = [call == "pd.DataFrame" for call in attributes]
        self.new_dfs.extend([name for name, is_df in zip(names, df_mask) if is_df ])
        


def isnotebook():
    try:
        shell = get_ipython().__class__.__name__
        if shell == 'ZMQInteractiveShell':
            return True   # Jupyter notebook or qtconsole
        elif shell == 'TerminalInteractiveShell':
            return False  # Terminal running IPython
        else:
            return False  # Other type (?)
    except NameError:
        return False      # Probably standard Python interpreter



