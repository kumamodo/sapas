import sapas
from sapas import TestItem

@sapas.param("--test", type=str, help="Custom user-defined parameter to be measured and validated against criteria.")

class ExArgs(TestItem):
    """
    [Example] How to define and use custom CLI parameters in a Sapas TestItem.
    
    [Parameter Registration]
    Use @sapas.param decorator to register custom parameters (backward-compatible with @sapas.arg). 
    Framework will automatically parse these parameters and make them accessible via `sapas.args` (or `self.args`).
    Usage: sapas custom_args.py --test sapas001
    """
    
    # 1. Base Configurations: Define file outputs, log folders, and filenames.
    #    The framework automatically initializes these files under the output directory.
    measure_file = "custom_args.txt"
    result_file = "custom_args_result.csv"
    criteria_file = "custom_args_criteria.csv"
    logs_folder = "CUSTOM_ARGS"
    logs_name = "custom_args.log"

    def run_test(self):
        """
        [Step 2: Core Test Logic & Execution]
        This is the main body where your test logic execution resides.
        """
        
        # 2. Accessing Arguments:
        #    After the framework parses the CLI input, the results can be accessed directly
        #    via `sapas.args.<your_parameter_name>` (or `self.args.<your_parameter_name>`).
        user_value = sapas.args.test
        
        # sapas.info outputs to the terminal and automatically flushes to the log file.
        sapas.info(f"Fetched custom argument from user: {user_value}")

        # 3. Setting Measurement (Mapping to Criteria):
        #    Assign the fetched value to `sapas.measure.<field_name>`.
        #    CRITICAL: The attribute name (USER_ARGS) must strictly match the 'Key' 
        #    defined in your criteria.csv for the automated PASS/FAIL evaluation to work.
        sapas.measure.USER_ARGS = user_value