SEVERITY_VALUES = {"Low": 1, "Moderate": 2, "High": 3, "Critical": 4}

def calculate_urgency(severity, affected_area, recurrence_count):
    severity_score = SEVERITY_VALUES.get(severity, 1) / 4 * 100
    area_score = max(0, min(float(affected_area), 100))
    recurrence_score = max(0, min(int(recurrence_count), 5)) / 5 * 100
    return round(0.50 * severity_score + 0.30 * area_score + 0.20 * recurrence_score, 2)

def priority_label(score):
    if score >= 75:
        return "Critical"
    if score >= 50:
        return "High"
    if score >= 25:
        return "Moderate"
    return "Low"
