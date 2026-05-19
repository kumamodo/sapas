from sapas import TestItem

class ExArgs(TestItem):
    """
    [Example] How to define and use custom CLI arguments in a Sapas TestItem.
    
    Use this pattern when your test script logic needs dynamic input from the 
    command line (e.g., specifying a target IP, custom timeout, or test tokens).
    """
    
    # 1. Base Configurations: Define file outputs, log folders, and filenames.
    #    The framework automatically initializes these files under the output directory.
    measure_file = "custom_args.txt"
    result_file = "custom_args_result.csv"
    criteria_file = "custom_args_criteria.csv"
    logs_folder = "CUSTOM_ARGS"
    logs_name = "custom_args.log"

    @classmethod
    def build_parser(cls, parser):
        """
        [Step 1: Argument Registration]
        This class method is automatically invoked by the framework during startup.
        You can leverage standard Python 'argparse' syntax to register custom arguments.
        
        Example: Registering a '--test' argument of string type.
        Usage: sapas custom_args.py --test sapas001
        """
        parser.add_argument(
            "--test", 
            type=str, 
            help="Custom user-defined parameter to be measured and validated against criteria."
        )

    def run_test(self):
        """
        [Step 2: Core Test Logic & Execution]
        This is the main body where your test logic execution resides.
        """
        
        # 2. Accessing Arguments:
        #    After the framework parses the CLI input, the results are injected into `self.args`.
        #    You can access the values directly via `self.args.<your_argument_name>`.
        user_value = self.args.test
        
        # self.log outputs to the terminal and automatically flushes to the log file.
        self.log(f"Fetched custom argument from user: {user_value}")

        # 3. Setting Measurement (Mapping to Criteria):
        #    Assign the fetched value to `self.measure.<field_name>`.
        #    CRITICAL: The attribute name (USER_ARGS) must strictly match the 'Key' 
        #    defined in your criteria.csv for the automated PASS/FAIL evaluation to work.
        self.measure.USER_ARGS = user_value