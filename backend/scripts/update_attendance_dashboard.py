from pathlib import Path

path = Path("backend/app/routers/attendance.py")
content = path.read_text(encoding="utf-8")

old_return = """    return DashboardResponse(
        organization_name=organization.name if organization else "",
        date=today,
        total_employees=total,
        present=present,
        late=late,
        not_checked_in=max(0, total - len(records)),
        pending_enrollments=max(0, total - scoped_enrolled),
    )"""

new_return = """    attention_items = []

    # 1. Provisional events needing confirmation
    prov_query = select(AttendanceEvent).where(
        AttendanceEvent.organization_id == organization_id,
        AttendanceEvent.provisional.is_(True),
        AttendanceEvent.confirmed_by_user_id.is_(None),
        AttendanceEvent.voided.is_(False),
    )
    if principal.branch_id is not None:
        prov_query = prov_query.where(AttendanceEvent.branch_id == principal.branch_id)
    prov_events = db.scalars(prov_query.order_by(AttendanceEvent.captured_at.desc()).limit(10)).all()
    provisional_count = len(prov_events)
    for pev in prov_events:
        attention_items.append(
            AttentionItem(
                category="PROVISIONAL_EVENT",
                title=f"Provisional Attendance Event ({pev.direction.value if hasattr(pev.direction, 'value') else pev.direction})",
                description=f"Standard assurance scan on {pev.captured_at.strftime('%H:%M')} requires admin review.",
                target_id=pev.id,
                action_url=f"/dashboard/attendance?highlight={pev.id}",
            )
        )

    # 2. Offline kiosks (not seen in past 15 minutes)
    fifteen_min_ago = datetime.now(timezone.utc) - timedelta(minutes=15)
    dev_query = select(AttendanceDevice).where(
        AttendanceDevice.organization_id == organization_id,
        AttendanceDevice.status == DeviceStatus.ACTIVE,
    )
    if principal.branch_id is not None:
        dev_query = dev_query.where(AttendanceDevice.branch_id == principal.branch_id)
    devices = db.scalars(dev_query).all()
    offline_devices = [d for d in devices if d.last_seen_at is None or d.last_seen_at.replace(tzinfo=timezone.utc) < fifteen_min_ago]
    offline_count = len(offline_devices)
    for dev in offline_devices[:5]:
        last_str = dev.last_seen_at.strftime("%b %d, %H:%M") if dev.last_seen_at else "Never"
        attention_items.append(
            AttentionItem(
                category="OFFLINE_KIOSK",
                title=f"Kiosk Offline: {dev.name}",
                description=f"Device has not communicated since {last_str}.",
                target_id=dev.id,
                action_url="/dashboard/devices",
            )
        )

    # 3. Unenrolled employees
    unenrolled_emps = [e for e in employees if e.id not in enrolled]
    for uemp in unenrolled_emps[:5]:
        attention_items.append(
            AttentionItem(
                category="UNENROLLED_EMPLOYEE",
                title=f"Missing Biometrics: {uemp.full_name}",
                description=f"Employee #{uemp.employee_code} has no active face profile.",
                target_id=uemp.id,
                action_url=f"/dashboard/employees/{uemp.id}",
            )
        )

    return DashboardResponse(
        organization_name=organization.name if organization else "",
        date=today,
        total_employees=total,
        present=present,
        late=late,
        not_checked_in=max(0, total - len(records)),
        pending_enrollments=max(0, total - scoped_enrolled),
        provisional_events_count=provisional_count,
        offline_devices_count=offline_count,
        attention_items=attention_items,
    )"""

assert old_return in content, "old_return not found"
content = content.replace(old_return, new_return)

# Also ensure AttentionItem is imported in attendance.py
if "AttentionItem" not in content:
    content = content.replace("DashboardResponse,", "AttentionItem,\n    DashboardResponse,")

path.write_text(content, encoding="utf-8")
print("Updated attendance.py dashboard successfully")

