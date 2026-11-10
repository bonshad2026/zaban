from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from zaban.db import Base
from zaban.models import Student


def _delete_rows(db: DBSession, table, condition) -> None:
    # Rows that point at the matching rows go first, so no foreign key is left dangling.
    for other in Base.metadata.tables.values():
        for fk in other.foreign_keys:
            if fk.column.table is table:
                referenced = select(fk.column).where(condition)
                _delete_rows(db, other, other.c[fk.parent.name].in_(referenced))
    db.execute(table.delete().where(condition))


def purge_web_children(db: DBSession) -> int:
    # Children created by a website adult (guardian_id is set) are removed with all their lessons, reports and payments.
    # Tenant API students have no guardian_id and are not touched. Returns how many children were removed.
    condition = Student.__table__.c.guardian_id.isnot(None)
    count = db.execute(select(Student.__table__.c.id).where(condition)).all()
    if count:
        _delete_rows(db, Student.__table__, condition)
    db.commit()
    return len(count)
