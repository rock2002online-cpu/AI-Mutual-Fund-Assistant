ZX2portfolio = [
    {"Fund": "Parag Parikh Flexi Cap", "Investment": 100000},
    {"Fund": "Motilal Oswal Midcap", "Investment": 50000},
    {"Fund": "Nifty 50 Index Fund", "Investment": 75000}
]

total = 0

for fund in portfolio:
    print(f"{fund['Fund']} : ₹{fund['Investment']}")
    total += fund["Investment"]

print("-" * 40)
print(f"Total Investment: ₹{total}")