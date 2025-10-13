"""Create base schema

Revision ID: 0001_create_base
Revises: 
Create Date: 2025-10-13 00:00:00

"""
from typing import Sequence, Union

from alembic import op
from sqlmodel import SQLModel

import models  # noqa: F401  # ensures SQLModel metadata is populated
import applications  # noqa: F401

# revision identifiers, used by Alembic.
revision: str = "0001_create_base"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    SQLModel.metadata.create_all(bind)


def downgrade() -> None:
    bind = op.get_bind()
    SQLModel.metadata.drop_all(bind)
