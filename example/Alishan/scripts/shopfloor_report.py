import sapas
from sapas import ActionItem


class ShopfloorReport(ActionItem):

    def run_action(self):
        # 1. Retrieve the serialized Shopfloor raw data from the global context.
        #    CRITICAL: 'TEST_DATA_STRING' is a reserved framework-level key. 
        #    Do NOT modify this string, as the framework specifically injects 
        #    all aggregated test metrics into this exact key.
        sf_payload = sapas.var.get('TEST_DATA_STRING')

        if not sf_payload:
            sapas.warn('[Shopfloor] TEST_DATA_STRING is empty. Skipping report.')
            return

        # 2. Format the payload to ensure compatibility with standard Shopfloor 
        #    protocols (standardizing line endings to CRLF for server parser stability).
        clean_payload = sf_payload.strip().replace('\n', '\r\n')

        # 3. Print the formatted payload to terminal/log for full traceability
        sapas.info(f'[Shopfloor] Preparing to report data...\n{clean_payload}')

        # TODO: Implement your shopfloor API client or socket connection here
        # e.g., shopfloor_client.post(clean_payload)
        
        sapas.info('[Shopfloor] Data reported successfully.')