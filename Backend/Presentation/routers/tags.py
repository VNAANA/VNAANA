"""/tags endpoints.

Public: tag names and IDs are not personal data. The frontend needs the IDs
to call PUT /users/{user_id}/tags with the topics a user picked by name.
"""

from fastapi import APIRouter

from Backend.Presentation.dependencies import TagServiceDep
from Backend.Presentation.schemas.common import TagRead

router = APIRouter(prefix="/tags", tags=["tags"])


@router.get("", response_model=list[TagRead])
def list_tags(service: TagServiceDep):
    return service.list_tags()
