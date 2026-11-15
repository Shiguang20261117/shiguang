"""作息模板 routines 的增删改查。"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import Routine, User
from ..schemas import RoutineCreate, RoutineRead, RoutineUpdate, apply_updates

router = APIRouter(prefix="/api/routines", tags=["作息模板"])


def _get_owned_routine(routine_id: int, user: User, db: Session) -> Routine:
    routine = db.get(Routine, routine_id)
    if routine is None or routine.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="作息模板不存在")
    return routine


@router.get("", response_model=list[RoutineRead])
def list_routines(
    weekday: int | None = Query(default=None, ge=0, le=6),
    is_active: bool | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Routine]:
    stmt = select(Routine).where(Routine.user_id == current_user.id)
    if weekday is not None:
        stmt = stmt.where(Routine.weekday == weekday)
    if is_active is not None:
        stmt = stmt.where(Routine.is_active == is_active)
    stmt = stmt.order_by(Routine.weekday, Routine.start_time)
    return list(db.scalars(stmt).all())


@router.post("", response_model=RoutineRead, status_code=status.HTTP_201_CREATED)
def create_routine(
    payload: RoutineCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Routine:
    routine = Routine(user_id=current_user.id, **payload.model_dump())
    db.add(routine)
    db.commit()
    db.refresh(routine)
    return routine


@router.get("/{routine_id}", response_model=RoutineRead)
def get_routine(
    routine_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Routine:
    return _get_owned_routine(routine_id, current_user, db)


@router.put("/{routine_id}", response_model=RoutineRead)
def update_routine(
    routine_id: int,
    payload: RoutineUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Routine:
    routine = _get_owned_routine(routine_id, current_user, db)
    data = payload.model_dump(exclude_unset=True)

    start = data.get("start_time", routine.start_time)
    end = data.get("end_time", routine.end_time)
    if start >= end:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, detail="结束时间必须晚于开始时间"
        )

    apply_updates(routine, data)
    db.commit()
    db.refresh(routine)
    return routine


@router.delete("/{routine_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_routine(
    routine_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    routine = _get_owned_routine(routine_id, current_user, db)
    db.delete(routine)
    db.commit()
