#!/bin/bash

# Script to fetch transaction data from Covalent API and save to JSON file
# Usage: ./src/utils/fetchAndImport.sh <address> <chain>

ADDRESS=$1
CHAIN=$2
OUTPUT_FILE="transactions-${ADDRESS:0:6}.json"

if [ -z "$ADDRESS" ] || [ -z "$CHAIN" ]; then
    echo "Usage: ./src/utils/fetchAndImport.sh <address> <chain>"
    echo "Example: ./src/utils/fetchAndImport.sh 0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045 eth-mainnet"
    exit 1
fi

echo "📥 Fetching transactions for $ADDRESS on $CHAIN..."
echo ""

# Fetch from API and save to file
curl -s "https://api.covalenthq.com/v1/${CHAIN}/address/${ADDRESS}/transactions_v2/?key=${GOLDRUSH_API_KEY}" \
    | jq '.data.items[]' > "$OUTPUT_FILE"

if [ -f "$OUTPUT_FILE" ]; then
    LINE_COUNT=$(wc -l < "$OUTPUT_FILE")
    TRANSACTION_COUNT=$((LINE_COUNT / 15))  # Rough estimate based on JSON structure
    
    echo "✓ Saved $TRANSACTION_COUNT transactions to $OUTPUT_FILE"
    echo ""
    echo "Now import to MongoDB with:"
    echo "  node src/utils/importTransactions.js \"$ADDRESS\" \"$CHAIN\" \"$OUTPUT_FILE\""
else
    echo "❌ Failed to fetch transactions"
    exit 1
fi
