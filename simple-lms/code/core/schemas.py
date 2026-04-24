from ninja import Schema, Field
from datetime import datetime
from typing import Optional, List

class Register(Schema):
    username: str
    password: str
    email: str
    first_name: str
    last_name: str

class UserOut(Schema):
    """Schema untuk data User yang dikembalikan dalam response."""
    id: int
    username: str
    first_name: str
    last_name: str
    email: str
    is_superuser: bool
    is_staff: bool
    is_active: bool

class CourseIn(Schema):
    name: str
    description: str
    price: int
    image: Optional[str] = ''

class CourseOut(Schema):
    """Schema untuk output data Course."""
    id: int
    name: str
    description: str
    price: int
    image: Optional[str] = ''
    teacher: UserOut
    created_at: datetime
    updated_at: datetime

class CourseMemberOut(Schema):
    id: int
    course_id: CourseOut
    roles: str
    created_at: Optional[datetime] = None

class ContentTitleOut(Schema):
    """Schema untuk menampilkan judul konten saja."""
    id: int
    name: str


class DetailCourseOut(CourseOut):
    """Schema untuk detail Course beserta daftar konten."""
    contents: List[ContentTitleOut] = Field(
        ..., alias="coursecontent_set"
    )

class CommentIn(Schema):
    comment: str
    content_id: int

class CommentUpdate(Schema):
    comment: str

class CourseContentIn(Schema):
    name: str
    description: str = '-'
    video_url: Optional[str] = None       
    course_id: int                         
    parent_id: Optional[int] = None       

class CourseContentOut(Schema):
    id: int
    name: str
    description: str
    video_url: Optional[str] = None
    course_id: int
    parent_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime