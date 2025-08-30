from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
from .Feedback import Feedback
from .Chapter import Chapter
from .Comment import Comment
from .Character import Character
from .Location import Location
from .Tag import Tag
from .News import News
from .Notification import Notification
from .SiteConfig import SiteConfig
from .TokenCostConfig import TokenCostConfig
from .User import User
from .CreditConfig import CreditConfig
from .Role import Role
from .CreditPackage import CreditPackage
from .ChapterGuide import ChapterGuide
from .GenerationLog import GenerationLog
from .Revenue import Revenue
from .StoryArc import StoryArc
from .Tag import Tag
from .Story import Story
