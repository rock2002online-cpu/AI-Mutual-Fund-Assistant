def currency(value):

    return f"₹{value:,.2f}"


def percentage(value):

    return f"{value:.2f}%"


def is_positive(value):

    return value >= 0