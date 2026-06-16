import sapas
from sapas import TestItem

@sapas.arg("--test", type=str, help="Custom user-defined parameter to be measured and validated against criteria.")

class ExArgs(TestItem):
    """
    [Example] How to define and use custom CLI arguments in a Sapas TestItem.
    
    [Argument Registration]
    Use @sapas.arg decorator to register custom arguments. 
    Framework will automatically parse these arguments and inject them into `self.args`.
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
        #    After the framework parses the CLI input, the results are injected into `self.args`.
        #    You can access the values directly via `self.args.<your_argument_name>`.
        user_value = self.args.test
        
        # sapas.info outputs to the terminal and automatically flushes to the log file.
        sapas.info(f"Fetched custom argument from user: {user_value}")

        # 3. Setting Measurement (Mapping to Criteria):
        #    Assign the fetched value to `sapas.measure.<field_name>`.
        #    CRITICAL: The attribute name (USER_ARGS) must strictly match the 'Key' 
        #    defined in your criteria.csv for the automated PASS/FAIL evaluation to work.
        sapas.measure.USER_ARGS = user_value