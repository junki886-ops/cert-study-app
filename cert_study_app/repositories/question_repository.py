from typing import Optional

from sqlalchemy import func, or_

from cert_study_app.models import Attempt, Question


class QuestionRepository:
    def __init__(self, db):
        self.db = db

    def _scope(self, source: Optional[str] = None, approved_only: bool = True):
        query = self.db.query(Question)
        if source:
            query = query.filter(Question.source == source)
        if approved_only:
            query = query.filter(Question.parse_status == "approved")
        return query

    def count(self, source: Optional[str] = None) -> int:
        return self._scope(source).count()

    def max_question_number(self, source: Optional[str] = None) -> int:
        value = self._scope(source).with_entities(func.max(Question.question_number)).scalar()
        return int(value or 0)

    def first(self, source: Optional[str] = None):
        return self._scope(source).order_by(Question.id.asc()).first()

    def get(self, question_id: int):
        return self.db.query(Question).filter(Question.id == question_id).first()

    def by_number(self, number: int, source: Optional[str] = None):
        query = self._scope(source).filter(Question.question_number == number)
        return query.order_by(Question.id.asc()).first()

    def by_number_any_status(self, number: int, source: Optional[str] = None):
        query = self.db.query(Question).filter(Question.question_number == number)
        if source:
            query = query.filter(Question.source == source)
        return query.order_by(Question.id.asc()).first()

    def random(self, source: Optional[str] = None, exclude_id: Optional[int] = None):
        query = self._scope(source)
        if exclude_id:
            query = query.filter(Question.id != exclude_id)
        return query.order_by(func.random()).first()

    def random_for_unit(
        self,
        source: Optional[str] = None,
        category: Optional[str] = None,
        subcategory: Optional[str] = None,
        exclude_id: Optional[int] = None,
    ):
        query = self._scope(source)
        if exclude_id:
            query = query.filter(Question.id != exclude_id)
        if category:
            query = query.filter(Question.category == category)
        if subcategory:
            query = query.filter(Question.subcategory == subcategory)
        return query.order_by(func.random()).first()

    def next_after(self, current_id: int, source: Optional[str] = None):
        return (
            self._scope(source)
            .filter(Question.id > current_id)
            .order_by(Question.id.asc())
            .first()
        )

    def previous_before(self, current_id: int, source: Optional[str] = None):
        return (
            self._scope(source)
            .filter(Question.id < current_id)
            .order_by(Question.id.desc())
            .first()
        )

    def first_for_type(
        self,
        source: Optional[str] = None,
        category: Optional[str] = None,
        question_type: Optional[str] = None,
    ):
        query = self._scope(source)
        if category:
            query = query.filter(Question.category == category)
        elif category == "":
            query = query.filter(or_(Question.category.is_(None), Question.category == ""))
        if question_type:
            query = query.filter(Question.question_type == question_type)
        return query.order_by(Question.id.asc()).first()

    def next_for_type(
        self,
        current_id: int,
        source: Optional[str] = None,
        category: Optional[str] = None,
        question_type: Optional[str] = None,
    ):
        query = self._scope(source).filter(Question.id > current_id)
        if category:
            query = query.filter(Question.category == category)
        elif category == "":
            query = query.filter(or_(Question.category.is_(None), Question.category == ""))
        if question_type:
            query = query.filter(Question.question_type == question_type)
        return query.order_by(Question.id.asc()).first()

    def previous_for_type(
        self,
        current_id: int,
        source: Optional[str] = None,
        category: Optional[str] = None,
        question_type: Optional[str] = None,
    ):
        query = self._scope(source).filter(Question.id < current_id)
        if category:
            query = query.filter(Question.category == category)
        elif category == "":
            query = query.filter(or_(Question.category.is_(None), Question.category == ""))
        if question_type:
            query = query.filter(Question.question_type == question_type)
        return query.order_by(Question.id.desc()).first()

    def questions_like(self, question: Question):
        query = self._scope(question.source)
        if question.category:
            query = query.filter(Question.category == question.category)
        if question.question_type:
            query = query.filter(Question.question_type == question.question_type)
        return query.order_by(Question.id.asc())

    def first_for_unit(
        self,
        source: Optional[str] = None,
        category: Optional[str] = None,
        subcategory: Optional[str] = None,
    ):
        query = self._scope(source)
        if category:
            query = query.filter(Question.category == category)
        if subcategory:
            query = query.filter(Question.subcategory == subcategory)
        return query.order_by(Question.id.asc()).first()

    def next_for_unit(
        self,
        current_id: int,
        source: Optional[str] = None,
        category: Optional[str] = None,
        subcategory: Optional[str] = None,
    ):
        query = self._scope(source).filter(Question.id > current_id)
        if category:
            query = query.filter(Question.category == category)
        if subcategory:
            query = query.filter(Question.subcategory == subcategory)
        return query.order_by(Question.id.asc()).first()

    def previous_for_unit(
        self,
        current_id: int,
        source: Optional[str] = None,
        category: Optional[str] = None,
        subcategory: Optional[str] = None,
    ):
        query = self._scope(source).filter(Question.id < current_id)
        if category:
            query = query.filter(Question.category == category)
        if subcategory:
            query = query.filter(Question.subcategory == subcategory)
        return query.order_by(Question.id.desc()).first()

    def source_summaries(self):
        return (
            self.db.query(
                Question.source,
                func.count(Question.id).label("question_count"),
                func.min(Question.id).label("first_question_id"),
                func.max(Question.id).label("last_question_id"),
            )
            .group_by(Question.source)
            .order_by(Question.source.asc())
            .all()
        )

    def add_attempt(self, user_id: str, question_id: int, chosen: Optional[str], correct: bool, note_type: Optional[str]):
        attempt = Attempt(
            user_id=user_id,
            question_id=question_id,
            chosen=chosen,
            correct=correct,
            note_type=note_type,
        )
        self.db.add(attempt)
        self.db.commit()
        return attempt

    def remove_attempts(self, user_id: str, question_id: int, note_type: str) -> int:
        deleted = (
            self.db.query(Attempt)
            .filter(
                Attempt.user_id == user_id,
                Attempt.question_id == question_id,
                Attempt.note_type == note_type,
            )
            .delete()
        )
        self.db.commit()
        return deleted

    def wrong_and_review(self, user_id: str, source: Optional[str] = None):
        query = (
            self.db.query(Attempt, Question)
            .join(Question, Attempt.question_id == Question.id)
            .filter(Attempt.user_id == user_id, Attempt.note_type.in_(["wrong", "review"]))
        )
        if source:
            query = query.filter(Question.source == source)
        return query.order_by(Attempt.id.desc()).all()

    def weak_type_summaries(self, user_id: str, source: Optional[str] = None):
        query = (
            self.db.query(
                Question.source,
                Question.category,
                Question.subcategory,
                func.count(Attempt.id).label("wrong_count"),
            )
            .join(Question, Attempt.question_id == Question.id)
            .filter(Attempt.user_id == user_id, Attempt.note_type == "wrong")
        )
        if source:
            query = query.filter(Question.source == source)
        return (
            query.group_by(Question.source, Question.category, Question.subcategory)
            .order_by(func.count(Attempt.id).desc())
            .all()
        )
