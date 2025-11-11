def vendor_day_bounds_str(d):
    # EXACT format the vendor requires (keep the space before 08:00)
    begin = f"{d}T00:00:00 08:00"
    end = f"{d}T23:59:59 08:00"
    return begin, end
