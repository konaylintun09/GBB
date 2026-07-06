"""Seed the database with demo data on first boot (matches the front-end demo)."""
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    ChecklistItem, ChecklistTemplate, Equipment, MaintenanceSchedule, User,
)
from app.security import hash_password
from app.util import add_months

DEMO_PASSWORD = "flowea123"  # change in production

USERS = [
    ("Admin", "User", "admin@flowea.io", "admin"),
    ("Field", "Engineer", "engineer@flowea.io", "engineer"),
    ("Maintenance", "Manager", "manager@flowea.io", "manager"),
    ("Customer", "Rep", "customer@flowea.io", "customer"),
    ("Company", "Leadership", "lead@flowea.io", "leadership"),
]

# tag, name, type, location, system, frequency, due-in-days, cooling_capacity, unit_type, site_name
EQUIPMENT = [
    ("EAF-EC-1-06A", "MV Fan", "MV Fan", "Energy Centre", "ACMV", "1M", -3, None, None, "Marina Bay Tower"),
    ("CH-L3-CHW-01", "Chiller Unit A", "Chiller", "L3 Plant Room", "ACMV", "3M", 4, "500 RT", "CHW", "Marina Bay Tower"),
    ("AHU-CM-01", "Air Handling Unit 1", "AHU", "Level 5", "ACMV", "3M", 2, "20000 CMH", "CHW", "Marina Bay Tower"),
    ("AHU-CM-02", "Air Handling Unit 2", "AHU", "Level 6", "ACMV", "1M", -2, "15000 CMH", "DX", "Marina Bay Tower"),
    ("PMP-B1-CWP-03", "Chilled Water Pump", "Pump", "Basement 1", "ACMV", "1M", -1, None, None, "Changi Logistics Hub"),
    ("FCU-L7-22", "Fan Coil Unit", "FCU", "Level 7", "ACMV", "1M", 6, "1200 CMH", "CHW", "Changi Logistics Hub"),
    ("CT-RF-02", "Cooling Tower", "Cooling Tower", "Rooftop", "ACMV", "6M", 48, None, None, "Changi Logistics Hub"),
    ("GEN-B2-01", "Diesel Generator", "Generator", "Basement 2", "Electrical", "12M", 120, None, None, "Changi Logistics Hub"),
    ("SWBD-L1-MSB", "Main Switchboard", "Switchboard", "Level 1", "Electrical", "6M", 60, None, None, "Marina Bay Tower"),
]

# Real AHU monthly checklist (15 items). Reading flags on the measurement rows.
AHU_1M = [
    ("1", "Record reading of temperature. Report any abnormal reading.", True, "°C"),
    ("2", "Record all readings of pressure. Report any abnormal reading.", True, "bar"),
    ("3", "Inspect and adjust all thermostat, safety cutouts and other automatic controls. Record all control and cutout settings.", False, None),
    ("4", "Check and report all defective gauges.", False, None),
    ("5", "Check and report all defective smoke detectors where provided.", False, None),
    ("6", "Check all air handling unit's filters for dust clogging.", False, None),
    ("7", "Where applicable, check and replace defective light bulbs in AHU.", False, None),
    ("8", "Check electrical connection.", False, None),
    ("9", "Check LCP components function.", False, None),
    ("10", "Check indicating lamps and replace if necessary.", False, None),
    ("11", "Record running ampere - L1. Report any abnormal reading.", True, "A"),
    ("12", "Record running ampere - L2. Report any abnormal reading.", True, "A"),
    ("13", "Record running ampere - L3. Report any abnormal reading.", True, "A"),
    ("14", "Record voltage reading (V).", True, "V"),
    ("15", "Record frequency (Hz).", True, "Hz"),
]

# Quarterly = monthly superset + 10 additional items (16-25).
AHU_3M = AHU_1M + [
    ("16", "Check and clean condensate drip tray and flush drain pipe of AHU.", False, None),
    ("17", "Inspect and clean air filters. Change when necessary.", False, None),
    ("18", "Inspect fan belts (if any) and adjust tension if necessary.", False, None),
    ("19", "Check all anti-vibration isolators for deterioration of rubber and spring.", False, None),
    ("20", "Check all air handling unit's filters for dust clogging.", False, None),
    ("21", "Lubricate all fan and motor bearings.", False, None),
    ("22", "Touch up and paint all rusty parts.", False, None),
    ("23", "Where applicable check and replace defective light bulbs in AHU.", False, None),
    ("24", "Check and comb all dented fins of coils if necessary.", False, None),
    ("25", "Check for deterioration of blower fan wheel and housing, align drive shaft if necessary.", False, None),
]

MV_FAN_1M = [
    ("A.1", "Check fan condition", False, None),
    ("A.2", "Check fan mounting", False, None),
    ("A.3", "Check motor condition", False, None),
    ("A.4", "Check belt condition", False, None),
    ("A.5", "Check bearing", False, None),
    ("A.6", "Check vibration", True, "mm/s"),
]


def _generic(eq_type: str, freq: str):
    base = [
        ("A.1", f"Visual inspection of {eq_type.lower()}", False, None),
        ("A.2", "Check mounting & fixings", False, None),
        ("A.3", "Check for leaks / corrosion", False, None),
        ("A.4", "Check operating temperature", True, "°C"),
        ("A.5", "Check noise / vibration", True, "mm/s"),
        ("A.6", "Clean & confirm safe operation", False, None),
    ]
    if freq == "1M":
        return base[:4]
    if freq == "12M":
        return base + [("B.1", "Full strip-down service", False, None)]
    return base


def items_for(eq_type: str, freq: str):
    if eq_type == "AHU":
        return list(AHU_1M) if freq == "1M" else list(AHU_3M)
    if eq_type == "MV Fan":
        items = list(MV_FAN_1M)
        if freq != "1M":
            items += [("B.1", "Megger test motor windings", True, "MΩ"), ("B.2", "Lubricate bearings", False, None)]
        return items
    return _generic(eq_type, freq)


async def seed(db: AsyncSession) -> None:
    existing = (await db.execute(select(User.id))).first()
    if existing:
        return  # already seeded

    for first, last, email, role in USERS:
        db.add(User(name=f"{first} {last}", first_name=first, last_name=last, email=email, role=role,
                    password_hash=hash_password(DEMO_PASSWORD)))

    types = set()
    for i, (tag, name, etype, loc, system, freq, due, capacity, unit_type, site) in enumerate(EQUIPMENT, start=1):
        next_due = date.today() + timedelta(days=due)
        last_done = add_months(next_due, -int(freq[:-1]) if freq != "12M" else -12)
        eq = Equipment(
            tag=tag, name=name, type=etype, location=loc, site_name=site, system=system,
            status="Active", qr_token=f"FLW-DEMO{i:03d}",
            cooling_capacity=capacity, unit_type=unit_type,
        )
        eq.schedule = MaintenanceSchedule(
            frequency=freq, interval_value=int(freq[:-1]), interval_unit="month",
            last_done=last_done, next_due=next_due,
        )
        db.add(eq)
        types.add(etype)

    # one checklist template per (type, frequency)
    for etype in types:
        for freq in ("1M", "3M", "6M", "12M"):
            tpl = ChecklistTemplate(equipment_type=etype, frequency=freq)
            tpl.items = [
                ChecklistItem(item_no=no, description=desc, requires_reading=rr, reading_unit=unit, sort_order=idx)
                for idx, (no, desc, rr, unit) in enumerate(items_for(etype, freq))
            ]
            db.add(tpl)

    await db.commit()
