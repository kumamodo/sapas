# -*- coding: utf-8 -*-

import csv
from pathlib import Path
from sapas.runtime.runtime import ctx
from sapas.modules.log import _log, info, error

from rich.table import Table
from rich.box import ASCII2
from rich.console import Console


class ResultManager:
    # --- Define index names consistent with the CSV/table ---
    COL_ITEM = 0
    COL_LSL = 1
    COL_USL = 2
    COL_MEASURED = 3
    COL_STATUS = 4
    COL_DESC = 5
    COL_ERRCODE = 6

    HEADER_LABELS = ['Test Item', 'LSL', 'USL', 'Measured', 'Status', 'Description', 'ErrCode']

    def __init__(self, out_path, criteria_file_name, txt_file_name):
        self.local_dir = Path(__file__).parent.resolve()

        workspace_root = Path(ctx.get('WORKSPACE_ROOT'))
        project_name = ctx.get('PROJECT_NAME')
        
        self.criteria_file = workspace_root / project_name / 'criteria' / criteria_file_name
        self.output_path = Path(out_path)
        
        self.test_result = {}
        # Keep the header included here, as this defines the structure of the output CSV.
        self.test_criteria = [self.HEADER_LABELS]
        
        self.fill_test_item_name = None

        if not self.criteria_file.exists():
            raise RuntimeError(f'Criteria file [{criteria_file_name}] not found...')

        with open(self.criteria_file, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            rows = list(reader)
            self.test_item_list = [row[0] for row in rows[1:]]
        
        info(f"Loaded {len(self.test_item_list)} test items.", tag='OUT')
        self._load_criteria_from_file(self.criteria_file)

        # Create the default measurement file
        default_measure_file = self.output_path / txt_file_name
        with open(default_measure_file, 'w', encoding='utf-8') as f:
            for item in self.test_item_list:
                f.write(f"{item}=fail\n")

        self.shopfloor_string = ""
        self.first_fail_code = "PASS"
        self.first_fail_desc = ""

    def __del__(self):
        info('Release aggregator class resource.', tag='OUT')

    def get_item_names(self):
        """
        Returns a clean list of item names read from the Criteria CSV.
        Used to create the MeasureProxy object during TestItem initialization.
        """
        return self.test_item_list

    def _load_measurements_from_file(self, filepath, dictionary):
        """Reads temporary key=value measurements from the txt file into a dictionary."""
        with open(filepath, "r", encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('item'):
                    try:
                        key, value = line.split("=", 1)
                        dictionary[key] = value
                    except ValueError:
                        continue

    def _load_criteria_from_file(self, filepath):
        """Reads standard target criteria CSV and appends data rows to test_criteria."""
        with open(filepath, "r", encoding='utf-8') as f:
            reader = csv.reader(f)
            header = next(reader)
            for row in reader:
                if row:
                    self.test_criteria.append(row)

    def _evaluate_item(self, val, c_min, c_max, err_raw):
        """
        Handles the Pass/Fail and ErrorCode logic for a single item.
        Returns: (result_str, final_error_code)
        """
        err_codes = str(err_raw).split(':')
        
        # 1. Attempt numeric comparison.
        try:
            f_val = float(val)
            f_min = float(c_min)
            f_max = float(c_max)

            if f_min <= f_val <= f_max:
                return 'PASS', 'None'
            
            # Numeric failure determination.
            if f_val < f_min:
                # Lower bound failure: take index 0 (if length is 2).
                code = err_codes[0] if len(err_codes) == 2 else err_codes[0]
                return 'FAIL', code
            elif f_val > f_max:
                # Upper bound failure: take index 1 (if length is 2).
                code = err_codes[1] if len(err_codes) == 2 else err_codes[0]
                return 'FAIL', code
            
            return 'FAIL', err_codes[0]

        except (ValueError, TypeError):
            # 2. Numeric conversion failed; proceed to string/special-case evaluation logic.
            if c_min == val == c_max:
                return 'PASS', 'None'
            
            if c_min == 'RECORD' and c_max == 'RECORD' and val != 'Exception' and val != 'NA':
                return 'PASS', 'None'
            
            # String evaluation failed.
            return 'FAIL', err_codes[0]

    def evaluate_and_render_report(self, test_value, criteria):
        """Evaluates all test data items and prints a stylized report table to the console."""
        self.shopfloor_string = ""

        console = Console(width=150)
        table = Table(
            title="[bold blue]Test Execution Report[/bold blue]", 
            box=ASCII2, 
            header_style="bold cyan",
            title_justify="left",
            # Reduce spacing pressure.
            collapse_padding=True
        )

        # Set no_wrap=True for all columns,
        # and apply max_width limits to columns that are prone to overflow.
        table.add_column(self.HEADER_LABELS[0], justify="center", style="white", no_wrap=True)
        table.add_column(self.HEADER_LABELS[1], justify="center", max_width=12, no_wrap=True)
        table.add_column(self.HEADER_LABELS[2], justify="center", max_width=12, no_wrap=True)
        table.add_column(
            self.HEADER_LABELS[3],
            justify="center",
            style="magenta",
            overflow="ellipsis",
            max_width=25,
            no_wrap=True
        )
        table.add_column(self.HEADER_LABELS[4], justify="center", no_wrap=True)
        table.add_column(
            self.HEADER_LABELS[5], 
            justify="center", 
            style="dim", 
            no_wrap=True, 
            overflow="ellipsis", 
            max_width=30
        )

        table.add_column(self.HEADER_LABELS[6], justify="center", no_wrap=True)

        for i in range(1, len(criteria)):
            row = criteria[i]
            item_name = row[self.COL_ITEM]
            val = test_value.get(item_name, "Exception")
            
            res, err = self._evaluate_item(
                val, row[self.COL_LSL], row[self.COL_USL], row[self.COL_ERRCODE]
            )

            item_name = row[self.COL_ITEM]
            val = test_value.get(item_name, "Exception")
            self.shopfloor_string += f"##{item_name}={val}\n"

            # Record the first encountered error code.
            if res != "PASS" and self.first_fail_code == "PASS":
                self.first_fail_code = err
                self.first_fail_desc = row[self.COL_DESC]

            # Update the data into the criteria array (for later CSV output).
            row[self.COL_MEASURED] = val
            row[self.COL_STATUS] = res
            row[self.COL_ERRCODE] = err

            status_display = f"[bold green]PASS[/bold green]" if res == "PASS" else f"[bold white on red]** {res} **[/bold white on red]"
            err_display = f"[dim]--[/dim]" if err == "None" else f"[bold yellow]{err}[/bold yellow]"
            val_display = f"[bold red]{val}[/bold red]" if val == "Exception" else str(val)
            display_name = item_name.format(self.fill_test_item_name) if self.fill_test_item_name else item_name

            table.add_row(
                display_name,
                str(row[self.COL_LSL]),
                str(row[self.COL_USL]),
                val_display,
                status_display,
                str(row[self.COL_DESC]),
                err_display
            )
        _log('OUT', table)

    def _export_final_csv(self, filepath, criteria_list):
        """Outputs the final calculated test evaluation rows to a result CSV file."""
        error_count = 0
        with open(filepath, "w", encoding='utf-8') as f:
            for index, row in enumerate(criteria_list):
                # Handle dynamic name injection.
                if self.fill_test_item_name and index != 0:
                    raw_str = ','.join(row).strip()
                    out_str = raw_str.format(self.fill_test_item_name)
                    # Log only the first occurrence of the message.
                    if index == 1:
                        info(f'[Result]: Re-filling [{self.fill_test_item_name}] for items...', tag='OUT')
                else:
                    out_str = ','.join(row).strip()

                f.write(out_str + '\n')

                # Count errors (skip header row at index 0).
                if index != 0:
                    if row[self.COL_STATUS] not in ['PASS', 'NA']:
                        error_count += 1

        info(f"{error_count} error(s) found", tag='OUT')
        return 80 if error_count > 0 else 0

    def process_test_results(self, txt_file, result_file, measure_value=None, dynamic_name=None):
        """Main orchestrator method to back up raw measurements, evaluate statuses, and generate outputs."""
        measure_value = measure_value or []
        self.fill_test_item_name = dynamic_name
        self.measure_file = self.output_path / txt_file
        self.result_file = self.output_path / result_file

        target_len = len(self.test_item_list) 
        
        # Automatically pad with exceptions if the provided measurement values are insufficient.
        while len(measure_value) < target_len:
            measure_value.append('Exception')

        info(f'Criteria items quantity: {target_len}', tag='OUT')
        
        # Safety check: ensure the counts are fully consistent.
        if len(measure_value) != target_len:
            # TODO: Print more information here to speed up debugging.
            raise RuntimeError(
                f'Quantity unequal: Criteria({target_len}) vs Measured({len(measure_value)})'
            )

        # --- Write the measurement values. ---
        if measure_value:
            info(f"Writing measurements to {txt_file}...", tag='OUT')
            with open(self.measure_file, 'w', encoding='utf-8') as f:
                # Iterate over names and values simultaneously using zip.
                for item_name, val in zip(self.test_item_list, measure_value):
                    f.write(f"{item_name}={val}\n")

        # Perform evaluation and generate the final report.
        self._load_measurements_from_file(self.measure_file, self.test_result)
        self.evaluate_and_render_report(self.test_result, self.test_criteria)
        return self._export_final_csv(self.result_file, self.test_criteria)