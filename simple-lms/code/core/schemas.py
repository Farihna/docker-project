"""
core/schemas.py
Pydantic schemas untuk Django Ninja API.

Progress 4 — tambahan:
  - AnalyticsOut : schema untuk response data analytics dari MongoDB
"""

from ninja import Schema, Field
from datetime import datetime
from typing import Optional, List


# =============================================================================
# Auth / User
# =============================================================================

class Register(Schema):
    username:   str
    password:   str
    email:      str
    first_name: str
    last_name:  str


class UserOut(Schema):
    """Data user yang dikembalikan dalam response."""
    id:           int
    username:     str
    first_name:   str
    last_name:    str
    email:        str
    is_superuser: bool
    is_staff:     bool
    is_active:    bool


# =============================================================================
# Course
# =============================================================================

class CourseIn(Schema):
    name:        str
    description: str
    price:       int
    image:       Optional[str] = ""


class CourseOut(Schema):
    """Output data Course."""
    id:          int
    name:        str
    description: str
    price:       int
    image:       Optional[str] = ""
    teacher:     UserOut
    created_at:  datetime
    updated_at:  datetime


class ContentTitleOut(Schema):
    """Judul konten saja (dipakai di DetailCourseOut)."""
    id:   int
    name: str


class DetailCourseOut(CourseOut):
    """Detail Course beserta daftar konten."""
    contents: List[ContentTitleOut] = Field(..., alias="coursecontent_set")


# =============================================================================
# CourseMember / Enrollment
# =============================================================================

class CourseMemberOut(Schema):
    id:         int
    course_id:  CourseOut
    roles:      str
    created_at: Optional[datetime] = None


# =============================================================================
# Comment
# =============================================================================

class CommentIn(Schema):
    comment:    str
    content_id: int


class CommentUpdate(Schema):
    comment: str


# =============================================================================
# CourseContent
# =============================================================================

class CourseContentIn(Schema):
    name:        str
    description: str = "-"
    video_url:   Optional[str] = None
    course_id:   int
    parent_id:   Optional[int] = None


class CourseContentOut(Schema):
    id:          int
    name:        str
    description: str
    video_url:   Optional[str] = None
    course_id:   int
    parent_id:   Optional[int] = None
    created_at:  datetime
    updated_at:  datetime


# =============================================================================
# Analytics (MongoDB)
# =============================================================================

class AnalyticsOut(Schema):
    """Schema untuk response data analytics enrollment dari MongoDB."""
    course_id:         int
    total_enrollments: int