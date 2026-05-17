class MeasureProxy:
    def __init__(self, item_names):
        # Create a dictionary with all values initialized to "NA".
        self._results = {name: "NA" for name in item_names}
        self._item_names = item_names

    def __getitem__(self, item):
        return getattr(self, item)

    def __setitem__(self, item, value):
        setattr(self, item, value)

    def __setattr__(self, name, value):
        # If it is a private attribute (prefixed with an underscore), handle it normally.
        if name.startswith('_'):
            super().__setattr__(name, value)
        # If it is an item name from the CSV, store it in the dictionary.
        elif name in self._results:
            self._results[name] = value
        else:
            # If the user defines a name that does not exist in the CSV,
            # immediately raise an error to notify them.
            raise AttributeError(f"\n[Sapas] Error: Test item does not exist in the CSV. '{name}'\n"
                                 f"Please check if {self._item_names} contains any spelling errors.")

    def __getattr__(self, name):
        if name in self._results:
            return self._results[name]
        raise AttributeError(f"Test item '{name}' does not exist.")

    def to_list(self):
        # Return a list in the original CSV order for use by the ResultManager.
        return [self._results[name] for name in self._item_names]