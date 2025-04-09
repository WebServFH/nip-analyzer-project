import ast
import csv
import functools
import io
import json
import logging
import os
import pickle
import random
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unicodedata
import warnings
from configparser import ConfigParser
from contextlib import contextmanager
from logging.handlers import QueueHandler, QueueListener, RotatingFileHandler
from multiprocessing import Manager, Pool
from pathlib import Path
import babel
import psutil
import timeout_decorator
from tqdm import tqdm

# Increase recursion limit if necessary
sys.setrecursionlimit(1500)


# Function to suppress warnings temporarily during progress bar updates
def suppress_warnings():
    warnings.filterwarnings("ignore", category=FutureWarning)
    warnings.filterwarnings("ignore", category=UserWarning)

# Function to redirect logs to file
def redirect_logs_to_file(log_file='processing_warnings.log'):
    # Setting up logging to file
    handler = RotatingFileHandler(log_file, maxBytes=100 * 1024, backupCount=2)
    logging.getLogger().addHandler(handler)
    

# Disk monitoring function
def check_disk_usage():
    usage = shutil.disk_usage('/')
    logging.info(f"Disk usage: {usage.free / (1024 ** 3):.2f} GB free of {usage.total / (1024 ** 3):.2f} GB")

# System stats logging function
def log_system_stats():
    disk_usage = psutil.disk_usage('/')
    logging.info(f"Disk usage: {disk_usage.free / (1024 ** 3):.2f} GB free")

    memory_info = psutil.virtual_memory()
    logging.info(f"Memory usage: {memory_info.percent}% used")

    process_count = len(psutil.pids())
    logging.info(f"Number of running processes: {process_count}")

def setup_logging():
    manager = Manager()
    log_queue = manager.Queue()
    # This log rotation to avoid large log files
    handler = RotatingFileHandler("processing.log", maxBytes=100 * 1024, backupCount=2)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)

    listener = QueueListener(log_queue, handler)
    listener.start()

    logging.basicConfig(level=logging.INFO, handlers=[QueueHandler(log_queue)])

    return log_queue, listener

def worker_init(log_queue):
    queue_handler = QueueHandler(log_queue)
    logger = logging.getLogger()
    logger.addHandler(queue_handler)
    logger.setLevel(logging.INFO)

def global_exception_handler(exc_type, exc_value, exc_traceback):
    logging.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))

def create_config_file():
    config = ConfigParser()
    config['paths'] = {
        'input_csv_file_path': 'input_csv_file_19.csv',
        'output_csv_file_path': 'analyze_error_handling_output.csv',
        'clone_dir': 'cloned_repos',
        'cache_file': 'analysis_cache.pkl'
    }
    with open('config.ini', 'w') as configfile:
        config.write(configfile)

def update_config_file():
    config = ConfigParser()
    config.read('config.ini')
    if 'paths' not in config:
        config['paths'] = {}
    config['paths']['input_csv_file_path'] = config.get('paths', 'input_csv_file_path', fallback='input_csv_file_19.csv')
    config['paths']['output_csv_file_path'] = config.get('paths', 'output_csv_file_path', fallback='analyze_error_handling_output.csv')
    config['paths']['clone_dir'] = config.get('paths', 'clone_dir', fallback='cloned_repos')
    config['paths']['cache_file'] = config.get('paths', 'cache_file', fallback='analysis_cache.pkl')
    with open('config.ini', 'w') as configfile:
        config.write(configfile)

def load_configuration():
    config = ConfigParser()
    config.read('config.ini')
    return config

@contextmanager
def open_file(file_path):
    encodings = ['utf-8', 'latin1', 'iso-8859-1', 'ascii', 'utf-16', 'utf-32', 'cp1252', 'cp850', 'mac_roman']
    for encoding in encodings:
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                yield f
            return  # If successful, exit the context manager
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError(f"Unable to decode {file_path} with any of the attempted encodings")


# Define parsing functions for different languages

def parse_python_code(code):
    error_handling_type = 'None'
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        logging.error(f"SyntaxError: Invalid Python code. Detail: {str(e)}")
        return error_handling_type  # Return early if the code cannot be parsed

    class ErrorHandlingVisitor(ast.NodeVisitor):
        def __init__(self):
            self.has_basic_handling = False
            self.has_advanced_handling = False

        def visit_Try(self, node):
            self.has_basic_handling = True
            if self.has_advanced_handling:
                return  # Stop traversal if both types are found
            self.generic_visit(node)

        def visit_ExceptHandler(self, node):
            self.has_basic_handling = True
            if self.has_advanced_handling:
                return  # Stop traversal if both types are found
            self.generic_visit(node)

        def visit_Call(self, node):
            if isinstance(node.func, ast.Name) and node.func.id.lower() in {"timeout", "retry", "circuitbreaker", "backoff"}:
                self.has_advanced_handling = True
            elif isinstance(node.func, ast.Attribute):
                if node.func.attr.lower() in {'status_code', 'raise_for_status'}:
                    self.has_basic_handling = True
            
            if self.has_basic_handling and self.has_advanced_handling:
                return  # Stop traversal if both types are found
            self.generic_visit(node)

        def visit_With(self, node):
            for item in node.items:
                if isinstance(item.context_expr, ast.Call):
                    if isinstance(item.context_expr.func, ast.Name) and item.context_expr.func.id.lower() in {"timeout", "retry", "circuitbreaker", "backoff"}:
                        self.has_advanced_handling = True
                        if self.has_basic_handling:
                            return  # Stop traversal if both types are found
            self.generic_visit(node)

    visitor = ErrorHandlingVisitor()
    visitor.visit(tree)

    if visitor.has_basic_handling and visitor.has_advanced_handling:
        error_handling_type = 'Both'
    elif visitor.has_advanced_handling:
        error_handling_type = 'Advanced'
    elif visitor.has_basic_handling:
        error_handling_type = 'Basic'

    return error_handling_type


def preprocess_java_code(code):
    # Remove BOM and normalize Unicode
    code = code.replace('\ufeff', '')
    code = unicodedata.normalize('NFKC', code)
    code = code.encode('utf-16', 'surrogatepass').decode('utf-16')

    # Additional preprocessing to handle problematic annotations
    code = re.sub(r'@(\w+)\s*(\([^)]*\))?\s*(?=class|interface|enum|@interface)', r'/* @\1\2 */', code)
    
    # Normalize line endings
    code = code.replace('\r\n', '\n').replace('\r', '\n')
    code = code.replace('\u2028', '\n').replace('\u2029', '\n')

    # Remove invalid control characters
    code = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F-\x9F]', '', code)

    # Standardize quote characters
    code = code.replace('’', "'").replace('“', '"').replace('”', '"')
    
    code = re.sub(r'("(?:[^"\\]|\\.)*$)', r'\1"', code)  # Close unclosed double quotes
    code = re.sub(r"('(?:[^'\\]|\\.)*$)", r"\1'", code)  # Close unclosed single quotes

    # Handle hash selectively (e.g., color codes)
    code = re.sub(r'#([0-9A-Fa-f]{6}|[0-9A-Fa-f]{3})(?!\w)', r'COLOR_\1', code)

    # Escape special characters and balance quotes
    code = re.sub(r'\\u([0-9A-Fa-f]{4})', lambda m: '\\u' + m.group(1).upper(), code)  # Normalize Unicode escapes to uppercase
    code = re.sub(r'"(.*?)"', lambda m: '"' + m.group(1).replace('#', '\\#').replace('\n', '\\n') + '"', code)
    code = re.sub(r'(\\*)"', lambda m: '@@QUOTE@@' if len(m.group(1)) % 2 == 0 else m.group(0), code)
    code = re.sub(r"(\\*)'", lambda m: "@@SINGLE_QUOTE@@" if len(m.group(1)) % 2 == 0 else m.group(0), code)
    code = re.sub(r'(\\+)', r'\\\\', code)

    # Handle emojis and symbols
    code = re.sub(r'[^\x00-\x7F]', lambda x: f'\\u{ord(x.group(0)):04x}', code)

    # Normalize block comments
    code = re.sub(r'/\*.*?\*/', '/* */', code, flags=re.DOTALL)
    code = re.sub(r'/\*.*$', '/* */', code, flags=re.DOTALL)

    # Remove line comments
    code = re.sub(r'//.*$', '', code, flags=re.MULTILINE)
    code = re.sub(r'/\*.*?\*/', '', code, flags=re.DOTALL)

    # Handle unescaped line breaks in strings
    def replace_newlines(match):
        return match.group(1) + match.group(2) + match.group(3).replace('\n', '\\n') + match.group(4) + match.group(2)

    code = re.sub(r'([^\\])(["\'`])(.*?)\n(.*?)\2', replace_newlines, code, flags=re.DOTALL)
    

    # Remove unwanted symbols (e.g., "So" category in Unicode)
    code = re.sub(r'[^\w\s#@,"\'(){}[\]<>;.:*/+=-]', '', code)

    # Ensure the code ends with a newline
    if not code.endswith('\n'):
        code += '\n'

    return code


def parse_java_code(code, advanced_methods=None, basic_methods=None):
    if advanced_methods is None:
        advanced_methods = {"timeout", "retry", "circuitbreaker", "backoff"}
    if basic_methods is None:
        basic_methods = {"catch", "finally", "throw", "throws", "statuscode"}

    error_handling_type = 'None'
    temp_file_path = None

    try:
        with tempfile.NamedTemporaryFile(mode='w+', suffix='.java', delete=False) as temp_file:
            temp_file_path = temp_file.name
            temp_file.write(code)

        jar_path = Path('target/your-artifact-id-1.0-SNAPSHOT.jar').resolve()
        
        result = subprocess.run(
            ['java', '-jar', str(jar_path), temp_file_path],
            capture_output=True,
            text=True,
            check=True
        )

        parsed_output = json.loads(result.stdout)
        has_basic_handling = parsed_output.get('hasBasicHandling', False)
        has_advanced_handling = parsed_output.get('hasAdvancedHandling', False)

        if has_basic_handling and has_advanced_handling:
            error_handling_type = 'Both'
        elif has_basic_handling:
            error_handling_type = 'Basic'
        elif has_advanced_handling:
            error_handling_type = 'Advanced'

    except subprocess.CalledProcessError as e:
        logging.error(f"Error running JavaParser analyzer: {e.stderr}")
        if e.stdout:
            try:
                parsed_output = json.loads(e.stdout)
                has_basic_handling = parsed_output.get('hasBasicHandling', False)
                has_advanced_handling = parsed_output.get('hasAdvancedHandling', False)
                if has_basic_handling and has_advanced_handling:
                    error_handling_type = 'Both'
                elif has_basic_handling:
                    error_handling_type = 'Basic'
                elif has_advanced_handling:
                    error_handling_type = 'Advanced'
            except json.JSONDecodeError:
                logging.error("Failed to parse partial results")
    except json.JSONDecodeError as e:
        logging.error(f"Error parsing JavaParser output: {e}")
    except Exception as e:
        logging.error(f"Unexpected error during Java parsing: {str(e)}")
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except Exception as e:
                logging.error(f"Error removing temporary file: {str(e)}")

    return error_handling_type 
    
          


# Additional Babel plugins for parsing javascript code
BABEL_PLUGINS = ['jsx', 'typescript', 'classProperties', 'objectRestSpread']

def parse_javascript_code(code):
    error_handling_type = 'None'
    temp_file_path = None  # Temporary file path for cleanup

    try:
        # Create a temporary file for the JavaScript code
        with tempfile.NamedTemporaryFile(mode='w+', suffix='.js', delete=False, encoding='utf-8') as temp_file:
            temp_file_path = temp_file.name
            temp_file.write(code)  # Write JavaScript code to the temp file

        # Run the JavaScript parser with a timeout
        result = subprocess.run(
            ['node', 'parse_javascript.js', temp_file_path],
            capture_output=True,
            text=True,
            check=True,
            timeout=30  # Set a 30-second timeout
        )

        # Parse the output from the Node.js script
        parsed_output = json.loads(result.stdout)
        has_basic_handling = parsed_output.get('hasBasicHandling', False)
        has_advanced_handling = parsed_output.get('hasAdvancedHandling', False)
        
        # Determine the error handling type
        if has_basic_handling and has_advanced_handling:
            error_handling_type = 'Both'
        elif has_basic_handling:
            error_handling_type = 'Basic'
        elif has_advanced_handling:
            error_handling_type = 'Advanced'

    except subprocess.TimeoutExpired:
        logging.error("JavaScript parsing timed out after 30 seconds")
    except subprocess.CalledProcessError as e:
        logging.error(f"Error running Babel parser: {e.stderr}")
    except json.JSONDecodeError as e:
        logging.error(f"Error parsing JSON output: {e}")
    except Exception as e:
        logging.error(f"Unexpected error in JavaScript parsing: {str(e)}")
    finally:
        # Clean up the temporary file
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except Exception as e:
                logging.error(f"Error removing temporary file: {str(e)}")

    return error_handling_type



def parse_typescript_code(code):
    error_handling_type = 'None'
    temp_file_path = None

    try:
        with tempfile.NamedTemporaryFile(mode='w+', suffix='.ts', delete=False) as temp_file:
            temp_file_path = temp_file.name
            temp_file.write(code)

        result = subprocess.run(
            ['node', 'parse_typescript.js', temp_file_path],
            capture_output=True,
            text=True,
            check=True
        )

        parsed_output = json.loads(result.stdout)
        has_basic_handling = parsed_output.get('hasBasicHandling', False)
        has_advanced_handling = parsed_output.get('hasAdvancedHandling', False)

        if has_basic_handling and has_advanced_handling:
            error_handling_type = 'Both'
        elif has_basic_handling:
            error_handling_type = 'Basic'
        elif has_advanced_handling:
            error_handling_type = 'Advanced'

    except subprocess.CalledProcessError as e:
        logging.error(f"Error running TypeScript parser: {e.stderr}")
        if e.stdout:
            logging.error(f"Parser stdout: {e.stdout}")
    except json.JSONDecodeError as e:
        logging.error(f"Error parsing JSON output: {e}")
        logging.error(f"Raw output: {result.stdout}")
    except Exception as e:
        logging.error(f"Unexpected error in TypeScript parsing: {str(e)}")
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.unlink(temp_file_path)
            except Exception as e:
                logging.error(f"Error removing temporary file: {str(e)}")

    return error_handling_type


def parse_go_code(code):
    error_handling_type = 'None'
    has_basic_handling = False
    has_advanced_handling = False
   

    try:
        # Save the Go code to a temporary file in the integration_test directory
        temp_file_path = os.path.join('integration_test', 'temp_go_code.go')
        with open(temp_file_path, 'w') as f:
            f.write(code)

        # Log the path and check if the file exists
        logging.info(f"Temp Go file created at: {temp_file_path}")
        if not os.path.exists(temp_file_path):
            logging.error("Temp Go file was not created.")
            return error_handling_type

        # Use subprocess to run the go/ast based parser
        result = subprocess.run(
            ['./parse_go_code/parse_go_code', temp_file_path],
            capture_output=True, text=True
        )
        output = result.stdout.strip()

        # Log the exact output from the Go parser for debugging
        logging.info(f"Go parser output: {output}")

        if not output:
            logging.error("Go parser returned empty output.")
            return error_handling_type

        try:
            has_basic_handling_str, has_advanced_handling_str = output.split(",")
            has_basic_handling = has_basic_handling_str.lower() == "true"
            has_advanced_handling = has_advanced_handling_str.lower() == "true"
        except ValueError:
            logging.error(f"Unexpected output format from Go parser: {output}")
            return error_handling_type

        if has_basic_handling and has_advanced_handling:
            error_handling_type = 'Both'
        elif has_basic_handling:
            error_handling_type = 'Basic'
        elif has_advanced_handling:
            error_handling_type = 'Advanced'

    except Exception as e:
        logging.error(f"Go parsing failed: {e}")
        
    """finally:
        # Clean up the temporary file
        if os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except OSError as e:
                logging.error(f"Failed to remove temporary file {temp_file_path}: {e}")
    """
    return error_handling_type


def parse_ruby_code(code):
    error_handling_type = 'None'
    temp_file_path = None
    
    with tempfile.NamedTemporaryFile(mode='w+', suffix='.rb', delete=False) as temp_file:
        temp_file_path = temp_file.name
        temp_file.write(code)

    try:
        result = subprocess.run(['ruby', 'parse_ruby.rb', temp_file_path], capture_output=True, text=True, check=True)

        output = result.stdout.strip()
        if not output:
            logging.error("Ruby parsing failed: No output from parser")
            return error_handling_type

        has_basic_handling, has_advanced_handling = output.split(',')

        if has_basic_handling == "true" and has_advanced_handling == "true":
            error_handling_type = 'Both'
        elif has_basic_handling == "true":
            error_handling_type = 'Basic'
        elif has_advanced_handling == "true":
            error_handling_type = 'Advanced'

    except subprocess.CalledProcessError as e:
        logging.error(f"Ruby parsing failed with exit code {e.returncode}. STDERR: {e.stderr.strip()}")
    except Exception as e:
        logging.error(f"Ruby parsing failed: {str(e)}")
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except Exception as e:
                logging.warning(f"Failed to remove temporary Ruby file {temp_file_path}: {str(e)}")

    return error_handling_type



def parse_ruby_code(code):
    error_handling_type = 'None'
    temp_file_path = None
    
    with tempfile.NamedTemporaryFile(mode='w+', suffix='.rb', delete=False) as temp_file:
        temp_file_path = temp_file.name
        temp_file.write(code)

    try:
        result = subprocess.run(['ruby', 'parse_ruby.rb', temp_file_path], capture_output=True, text=True, check=True)

        output = result.stdout.strip()
        if not output:
            logging.error("Ruby parsing failed: No output from parser")
            return error_handling_type

        has_basic_handling, has_advanced_handling = output.split(',')

        if has_basic_handling == "true" and has_advanced_handling == "true":
            error_handling_type = 'Both'
        elif has_basic_handling == "true":
            error_handling_type = 'Basic'
        elif has_advanced_handling == "true":
            error_handling_type = 'Advanced'

    except subprocess.CalledProcessError as e:
        logging.error(f"Ruby parsing failed with exit code {e.returncode}. STDERR: {e.stderr.strip()}")
    except Exception as e:
        logging.error(f"Ruby parsing failed: {str(e)}")
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except Exception as e:
                logging.warning(f"Failed to remove temporary Ruby file {temp_file_path}: {str(e)}")

    return error_handling_type


# Add a global flag to set the csharp parser path
C_SHARP_PARSER_PATH = os.path.abspath("/Users/francisobeng/Developer/Web_Services/Web_Services/NEW_AST_WEBSERVFH/CSharpParser/bin/Release/net8.0/CSharpParser.dll")

def parse_csharp_code(code):
    error_handling_type = 'None'
    temp_file_path = None
    
    if not os.path.exists(C_SHARP_PARSER_PATH):
        logging.error(f"C# parsing failed: '{C_SHARP_PARSER_PATH}' not found.")
        return error_handling_type

    try:
        # Create a temporary file with proper permissions in a secure location
        with tempfile.NamedTemporaryFile(mode='w+', suffix='.cs', delete=False) as temp_file:
            temp_file_path = temp_file.name
            temp_file.write(code)  

        # Execute the CSharpParser DLL
        result = subprocess.run(
            ['dotnet', C_SHARP_PARSER_PATH, temp_file_path], 
            capture_output=True, 
            text=True
        )

        if result.returncode != 0:
            logging.error(f"C# parsing failed with exit code {result.returncode}")
            logging.error(f"STDERR: {result.stderr.strip()}")
            return error_handling_type

        output = result.stdout.strip()
        if not output or ',' not in output:
            logging.error(f"Unexpected output format from C# parser: {output}")
            return error_handling_type

        has_basic_handling, has_advanced_handling = output.split(",")

        if has_basic_handling.lower() == "true" and has_advanced_handling.lower() == "true":
            error_handling_type = 'Both'
        elif has_basic_handling.lower() == "true":
            error_handling_type = 'Basic'
        elif has_advanced_handling.lower() == "true":
            error_handling_type = 'Advanced'

    except Exception as e:
        logging.error(f"C# parsing failed: {e}")
    
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except Exception as e:
                logging.error(f"Error removing C# temporary file: {str(e)}")

    return error_handling_type



# Add a global flag to track if the Kotlin compiler was already checked
JAVA_COMPILER_AVAILABLE = shutil.which('java') is not None


def parse_kotlin_code(code):
    global JAVA_COMPILER_AVAILABLE
    error_handling_type = 'None'
    temp_file_path = None
    jar_path = os.path.abspath('parse_kotlin.jar')

    if not os.path.exists(jar_path):
        logging.error(f"parse_kotlin.jar not found at {jar_path}")
        return error_handling_type

    if not JAVA_COMPILER_AVAILABLE:
        logging.error("Java not found. Please ensure Java is installed and accessible.")
        return error_handling_type

    with tempfile.NamedTemporaryFile(mode='w+', suffix='.kt', delete=False) as temp_file:
        temp_file_path = temp_file.name
        temp_file.write(code)
        temp_file.close()

    try:
        result = subprocess.run(
            ['java', '-jar', jar_path, temp_file_path], 
            capture_output=True, text=True, check=True
        )

        output = result.stdout.strip()
        if not output:
            logging.error("Kotlin parsing failed: No output from parser")
            return error_handling_type

        values = output.split(',')
        if len(values) != 2:
            logging.error(f"Kotlin parsing failed: Expected 2 values, but got {len(values)}: '{output}'")
            return error_handling_type

        has_basic_handling, has_advanced_handling = values
        
        if has_basic_handling == "true" and has_advanced_handling == "true":
            error_handling_type = 'Both'
        elif has_basic_handling == "true":
            error_handling_type = 'Basic'
        elif has_advanced_handling == "true":
            error_handling_type = 'Advanced'

    except subprocess.CalledProcessError as e:
        logging.error(f"Kotlin parsing failed with exit code {e.returncode}")
        logging.error(f"STDERR: {e.stderr.strip()}")
        logging.error(f"STDOUT: {e.stdout.strip()}")
    except Exception as e:
        logging.error(f"Kotlin parsing failed: {e}")
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except Exception as e:
                logging.error(f"Error removing Kotlin temporary file: {str(e)}")

    return error_handling_type


# Add a global flag to track if the sourcekitten tool was already checked
SOURCEKITTEN_AVAILABLE = shutil.which('sourcekitten') is not None

def parse_swift_code(code):
    global SOURCEKITTEN_AVAILABLE
    error_handling_type = 'None'
    has_basic_handling = False
    has_advanced_handling = False
    temp_file_path = None

    try:
        if not SOURCEKITTEN_AVAILABLE:
            logging.error("Swift parsing failed: 'sourcekitten' is not installed and accessible.")
            return error_handling_type

        with tempfile.NamedTemporaryFile(mode='w+', suffix='.swift', delete=False) as temp_file:
            temp_file_path = temp_file.name
            temp_file.write(code)
            temp_file.flush()

        logging.info(f"Temporary Swift file created at: {temp_file_path}")

        result = subprocess.run(['sourcekitten', 'structure', '--file', temp_file_path], capture_output=True, text=True)

        if result.returncode != 0:
            logging.error(f"Swift parsing failed with exit code {result.returncode}. STDERR: {result.stderr}")
            return error_handling_type

        if not result.stdout.strip():
            logging.error("Swift parsing failed: No output from parser")
            return error_handling_type

        try:
            ast = json.loads(result.stdout)
        except json.JSONDecodeError:
            logging.warning("Parse JSON output failed. Falling back to raw output analysis.")
            ast = result.stdout

        def traverse(node):
            nonlocal has_basic_handling, has_advanced_handling
            if isinstance(node, dict):
                if node.get('key.kind') == 'source.lang.swift.stmt.do':
                    has_basic_handling = True
                if node.get('key.name') in {"timeout", "retry", "CircuitBreaker", "backoff"}:
                    has_advanced_handling = True
                if node.get('key.name') == 'statusCode':
                    has_basic_handling = True

                for value in node.values():
                    traverse(value)
            elif isinstance(node, list):
                for item in node:
                    traverse(item)
            elif isinstance(node, str):
                # Fallback: check for keywords in raw string output
                lower_node = node.lower()
                if 'do' in lower_node or 'catch' in lower_node or 'try' in lower_node:
                    has_basic_handling = True
                if any(keyword in lower_node for keyword in ["timeout", "retry", "circuitbreaker", "backoff"]):
                    has_advanced_handling = True
                if 'statuscode' in lower_node:
                    has_basic_handling = True

        traverse(ast)

        if has_basic_handling and has_advanced_handling:
            error_handling_type = 'Both'
        elif has_basic_handling:
            error_handling_type = 'Basic'
        elif has_advanced_handling:
            error_handling_type = 'Advanced'

    except Exception as e:
        logging.error(f"Swift parsing failed: {e}")

    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except Exception as e:
                logging.warning(f"Failed to remove temporary file {temp_file.name}: {e}")

    return error_handling_type



@functools.lru_cache(maxsize=128)
def clone_repo(repo_url, clone_path, retries=3, delay=5, backoff_factor=2):
    attempt = 0
    while attempt < retries:
        try:
            if os.path.exists(clone_path):
                cleanup_clone(clone_path)

            logging.info(f"Cloning repository {repo_url}, attempt {attempt + 1}")
            subprocess.run(['git', 'clone', '--depth', '1', repo_url, clone_path], check=True, capture_output=True, text=True, timeout=300)
            logging.info(f"Successfully cloned {repo_url}")
            return True
        except subprocess.CalledProcessError as e:
            logging.error(f"Error cloning repository {repo_url}: {e.stderr.strip()}")
            attempt += 1
            sleep_time = delay + (random.uniform(0, 1) * backoff_factor)
            logging.info(f"Retrying in {sleep_time:.2f} seconds (attempt {attempt}/{retries})")
            time.sleep(sleep_time)
            delay *= backoff_factor

    logging.error(f"Failed to clone repository {repo_url} after {retries} attempts.")
    return False

def analyze_code(repo_path):
    error_handling_type = 'None'
    exception_files = set()
    languages_used = set()

    extension_to_language = {
        '.py': 'python', '.java': 'java', '.js': 'javascript',
        '.ts': 'typescript', '.go': 'go', '.php': 'php', 
        '.rb': 'ruby', '.cs': 'csharp', '.kt': 'kotlin', 
        '.swift': 'swift'
    }

    language_parsers = {
        'python': parse_python_code,
        'java': parse_java_code,
        'javascript': parse_javascript_code,
        'typescript': parse_typescript_code,
        'go': parse_go_code,
        'ruby': parse_ruby_code,
        'csharp': parse_csharp_code,
        'kotlin': parse_kotlin_code,
        'swift': parse_swift_code
    }

    files_to_analyze = [
        os.path.join(root, file)
        for root, _, files in os.walk(repo_path)
        for file in files
        if any(file.endswith(ext) for ext in extension_to_language.keys())
    ]

    for file_path in files_to_analyze:
        if not os.path.exists(file_path):
            logging.warning(f"File not found: {file_path}")
            continue
        
        
        try:
            with open_file(file_path) as f:
                file_extension = os.path.splitext(file_path)[1]
                language = extension_to_language.get(file_extension, "Unknown")
                parser = language_parsers.get(language)
            
                if parser:
                    code = f.read()
                    result = parser(code)

                    if result != 'None':
                        exception_files.add(file_path)
                        languages_used.add(language)
                        if error_handling_type == 'None':
                            error_handling_type = result
                        elif error_handling_type == 'Basic' and result == 'Advanced':
                            error_handling_type = 'Both'
                        elif error_handling_type == 'Advanced' and result == 'Basic':
                            error_handling_type = 'Both'

        except FileNotFoundError:
            logging.warning(f"File not found when trying to open: {file_path}")
            continue
    
        
        except UnicodeDecodeError:
            logging.warning(f"Skipping file due to encoding issues: {file_path}")
            continue
        
        except Exception as e:
            logging.error(f"Unexpected error processing file {file_path}: {str(e)}")
            continue

    return error_handling_type, list(exception_files), list(languages_used)



def process_repo(row, clone_dir):
    try:
        log_system_stats()
        check_disk_usage()

        repo_url = row['repo_url']
        repo_name = repo_url.split('/')[-1].replace('.git', '')
        clone_path = os.path.join(clone_dir, repo_name)

        logging.info(f'Processing repository {repo_url}...')
        if clone_repo(repo_url, clone_path, retries=3, delay=5, backoff_factor=2):
            if not os.listdir(clone_path):
                logging.error(f"Clone respository {repo_name} is empty")
                return None
            
            logging.info(f'Analyzing repository {repo_name}...')
            error_handling_type, exception_files, languages_used = analyze_code(clone_path)
            recommendation = get_recommendation(error_handling_type)
            languages_str = '; '.join(languages_used)

            cleanup_clone(clone_path)

            return {
                'repo_url': repo_url,
                'Exception Type': error_handling_type,
                'Recommendation': recommendation,
                'Languages': languages_str
            }
        else:
            logging.error(f"Failed to clone repository: {repo_url}")
            return None
    except Exception as e:
        logging.exception(f"Error processing repository {row['repo_url']}: {str(e)}")
        return None


def get_recommendation(error_handling_type):
    if error_handling_type == 'Both':
        return 'The codebase has basic and advanced exception handling.'
    elif error_handling_type == 'Advanced':
        return 'The codebase has advanced exception handling.'
    elif error_handling_type == 'Basic':
        return 'Basic exception handling detected. Consider enhancements.'
    else:
        return 'No exception handling detected. Consider adding exception handling.'

def cleanup_clone(clone_path):
    try:
        shutil.rmtree(clone_path)
        logging.info(f"Successfully removed directory {clone_path}")
    except Exception as e:
        logging.error(f"Failed to remove directory {clone_path}: {str(e)}")

def save_cache_incrementally(cache, cache_file, batch_size=1000):
    temp_cache = {}
    for i, (key, value) in enumerate(cache.items()):
        temp_cache[key] = value
        if (i + 1) % batch_size == 0:
            try:
                with open(cache_file, 'ab') as f:
                    pickle.dump(temp_cache, f)
                temp_cache.clear()
            except OSError as e:
                logging.error(f"Failed to save cache batch: {e}")

    if temp_cache:
        try:
            with open(cache_file, 'ab') as f:
                pickle.dump(temp_cache, f)
        except OSError as e:
            logging.error(f"Failed to save final cache batch: {e}")

def batch_process_repositories(rows, batch_size, log_queue, clone_dir):
    total_batches = (len(rows) + batch_size - 1) // batch_size
    
    redirect_logs_to_file()  # Redirect logs to file to avoid distracting progress bar
    suppress_warnings()  # Suppress specific warnings during processing
    
    for i in range(0, len(rows), batch_size):
        batch = rows[i:i + batch_size]
        logging.info(f"Processing batch {i // batch_size + 1}/{total_batches}...")

        log_system_stats()

        with Pool(processes=os.cpu_count(), initializer=worker_init, initargs=(log_queue,)) as pool:
            results = list(tqdm(
                pool.imap_unordered(functools.partial(process_repo, clone_dir=clone_dir), batch),
                total=len(batch),
                desc=f"Processing batch {i // batch_size + 1}/{total_batches}"
            ))
        yield results


def main():
    log_queue, listener = setup_logging()
    sys.excepthook = global_exception_handler

    config = load_configuration()
    input_csv_file_path = config.get('paths', 'input_csv_file_path')
    output_csv_file_path = config.get('paths', 'output_csv_file_path')
    clone_dir = config.get('paths', 'clone_dir')
    cache_file = config.get('paths', 'cache_file')

    if not os.path.exists(clone_dir):
        os.makedirs(clone_dir)

    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'rb') as f:
                cache = pickle.load(f)
        except (EOFError, pickle.UnpicklingError):
            logging.warning(f"Cache file {cache_file} is corrupted. Starting with an empty cache.")
            cache = {}
    else:
        cache = {}

    try:
        with open(input_csv_file_path, mode='r', newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            rows = list(reader)
    except Exception as e:
        logging.error(f"Failed to read input CSV file: {e}")
        listener.stop()
        sys.exit(1)

    total_repos = len(rows)
    logging.info(f"Total repositories in input CSV: {total_repos}")

    batch_size = 50 #batch size is set to 50 per a batch.

    try:
        with open(output_csv_file_path, mode='w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['repo_url', 'Exception Type', 'Recommendation', 'Languages']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
    except Exception as e:
        logging.error(f"Failed to write to output CSV file: {e}")
        listener.stop()
        sys.exit(1)

    for batch_results in batch_process_repositories(rows, batch_size, log_queue, clone_dir):
        successful_ops = sum(1 for result in batch_results if result is not None)
        failed_ops = len(batch_results) - successful_ops

        logging.info(f"Successful operations in batch: {successful_ops}")
        logging.info(f"Failed operations in batch: {failed_ops}")

        for result in batch_results:
            if result:
                cache[result['repo_url']] = result

        save_cache_incrementally(cache, cache_file)

        try:
            with open(output_csv_file_path, mode='a', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writerows(result for result in batch_results if result)
        except Exception as e:
            logging.error(f"Error writing to the CSV file: {e}")

    logging.info(f"Total repositories processed: {total_repos}")
    logging.info(f"Repositories in output CSV: {len(cache)}")

    listener.stop()

if __name__ == '__main__':
    if not os.path.exists('config.ini'):
        create_config_file()
    else:
        update_config_file()

    main()
