# WebServFH aka NIP (Nobody's Perfect)

The WebServFH tool is a Python utility designed to automate and enhance Exception Handling analysis in Web Service Applications from GitHub across nine (9) programming languages.

The WebServFH is called NIP for preferability in our research paper.

## Features
- Exception Handling Categorization
- Exception Handling Recommendation
- Multilanguage support for error handling analysis.
- Comprehensive system and process logging.
- Configuration via INI files for easy customization.
- Temporary file management for secure and clean parsing execution.

## Languages WebServFH supports:
- Python
- Java
- JavaScript
- TypeScript
- C#
- Go
- Ruby
- Kotlin
- Swift
## Note all the above languages must be installed on the local machine where the user wants to run WebServFH.


##Installations/Configurations
- Create a repository on your machine and name it "NEW_AST_WEBSERVFH"
- Clone the repo into the created folder on your machine by using "https://github.com/WebServFH/nip-analyzer-project.git"
- Launch your IDE, preferably VS Code, and navigate to the project directory "NEW_AST_WEBSERVFH" using the terminal.
- Install dependencies by running "pip install -r requirements.txt"
- Modify the config.ini file to set paths and other configurations specific to your environment:

  ##paths
     - input_csv_file_path = path/to/your/input.csv
     - output_csv_file_path = path/to/your/output.csv
     - clone_dir = path/to/your/clones
     - cache_file = path/to/your/cache.pkl
     - Path modification in "create_config_file()" should matcth "update_config_file()"
     
     
## Using the VS Code terminal, run "python WebServFH.py"



## Note: The WebServFH.py works with all files and folders in this project; however, it  does not depend on the folders listed below. 
      –– Exception_Handling_Analysis_Output Folder
      –– Experiment Folder
      –– GitHub_Repo_Details

## Recommendation: If you have a large input dataset like the one in the GitHub_Repo_Details folder, divide it into 1000 or 2000 per input data. There should be a "repo_url" column in your input dataset because "repo_url" is the main parameter for the WebServFH.py execution.
    
    
    



