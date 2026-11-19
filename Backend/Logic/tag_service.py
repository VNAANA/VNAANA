from Backend.Logic.domain.tag import Tag
from Backend.Logic.ports.tag_repository import TagRepository


class TagService:
    def __init__(self, tags: TagRepository):
        self.tags = tags

    def list_tags(self) -> list[Tag]:
        return self.tags.list_all()
