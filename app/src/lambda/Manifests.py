import logging
import json
from dataclasses import dataclass
from marshmallow import Schema, fields

logger = logging.getLogger(__name__)


@dataclass
class TextractDict:
  AnalyzeDocumentModelVersion: str
  Blocks: list
  DocumentMetadata: dict
  JobStatus: str
  NextToken: str
  StatusMessage: str
  Warnings: str


class TextractSchema(Schema):
  class Meta:
    ordered = True

  AnalyzeDocumentModelVersion = fields.Str(required=True)
  Blocks = fields.List(fields.Dict(), required=True)
  DocumentMetadata = fields.Dict()
  JobStatus = fields.Str(required=True)
  NextToken = fields.Str(required=False)
  StatusMessage = fields.Str(required=False)
  Warnings = fields.Str(required=False)


class tManifest:

  def __init__(self, tjson):
    self._modelVersion = tjson["AnalyzeDocumentModelVersion"]
    self._blocks = None
    self._docMeta = tjson["DocumentMetadata"]
    self._status = tjson["JobStatus"]
    self._nextToken = tjson["NextToken"] if "NextToken" in tjson else None
    self._statusMsg = tjson["StatusMessage"] if "StatusMessage" in tjson else None
    self._warnings = tjson["Warnings"] if "Warnings" in tjson else None

  '''
  Removes None type from JSON created by Textract async
  this makes it consumable for TRP
  '''

  def __remove_none(self, obj):
    if isinstance(obj, (list, tuple, set)):
      return type(obj)(self.__remove_none(x) for x in obj if x is not None)
    elif isinstance(obj, dict):
      return type(obj)((self.__remove_none(k), self.__remove_none(v))
                       for k, v in obj.items()
                       if k is not None and v is not None)
    else:
      return obj

  @property
  def tManifest(self):
    txtrct = TextractDict(self._modelVersion, self._blocks, self._docMeta,
                          self._status, None, None, None)
    schema = TextractSchema()
    return schema.dump(txtrct)

  @property
  def blocks(self):
    return self._blocks

  @property
  def toJson(self):
    data = self.tManifest
    return data
    
  def add_blocks(self, blocks):
    self._blocks = self.__remove_none(blocks)
