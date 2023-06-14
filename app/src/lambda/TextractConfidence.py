
import logging
import os
import json
from trp import Document

logger = logging.getLogger(__name__)

class tConf:
    def __init__(self, j: dict, log_level: str ='INFO'):
        self.json_data=j
        self.tDoc = Document(j)
        self.page_num = j["Blocks"][0]["Page"] # assuming j contains only 1 page
        logger.setLevel(log_level)

    @property
    def page_num(self):
        return self.page_num

    @property
    def tDocument(self):
        return self.tDoc
    
    '''
    Check confidence threshold for WORD and LINE
    '''
    # def eval_line_confidence(self, confidence_threshold: float):                         
    #     lines = []  
    #     for page in self.tDoc.pages:
    #         # lines and words
    #         logger.debug("Evaluating Lines...")
    #         for line in page.lines:
    #             if  line.confidence < confidence_threshold:   
    #                 logger.debug("Found low score lines...")
    #                 return True
    #     return False
    
    '''
    Check confidence threshold for WORD and LINE
    '''
    def eval_word_confidence(self, confidence_threshold: float):                         
        words = []  
        for page in self.tDoc.pages:
            # lines and words
            logger.debug("Evaluating Words...")
            for line in page.lines:
                for word in line.words:
                    if  word.confidence < confidence_threshold:   
                        logger.debug("Found low score words...")                     
                        return True
        return False

    '''
    Check confidence threshold for TABLE
    '''
    def eval_table_confidence(self, confidence_threshold: float):
        for page in self.tDoc.pages:        
            for table in page.tables:
                if table.confidence < confidence_threshold:  
                    logger.debug("Found low score table structure...")                            
                    return True                           
        return False

    '''
    Check confidence threshold for CELL
    '''
    def eval_cell_confidence(self, confidence_threshold: float):
        for page in self.tDoc.pages:        
            for table in page.tables:
                for r, row in enumerate(table.rows):
                    for c, cell in enumerate(row.cells):
                        if cell.confidence < confidence_threshold:  
                            logger.debug("Found low score cells structure...")                            
                            return True                           
        return False

    '''
    Check confidence threshold for FORM Keys
    '''
    def eval_form_key_confidence(self, confidence_threshold: float):                        
        for page in self.tDoc.pages:            
            for field in page.form.fields:
                if field.key.confidence < confidence_threshold:
                    logger.debug("Found low score kv pairs in form...")  
                    '''
                    this is geo for key-value pair as a whole for highlighting purposes for SMGT CHE.
                    Key and value level Geos are also available via field.key.geometry.polygon &
                    field.value.geometry.polygon but is not currently required. 
                    Available attrubutes
                    - field.key, field.value --> are the texts for key and values
                    - field.confidence, field.key.confidence, field.value.confidence
                    - field.id, field.key.id, field.value.id
                    - field.geometry, field.key.geometry, field.value.geometry // send key and values
                    '''                       
                    return True
        return False

    '''
    Check confidence threshold for FORM Values
    '''
    def eval_form_value_confidence(self, confidence_threshold: float):                        
        for page in self.tDoc.pages:            
            for field in page.form.fields:
                if field.value.confidence < confidence_threshold:
                    logger.debug("Found low score kv pairs in form...")  
                    '''
                    this is geo for key-value pair as a whole for highlighting purposes for SMGT CHE.
                    Key and value level Geos are also available via field.key.geometry.polygon &
                    field.value.geometry.polygon but is not currently required. 
                    Available attrubutes
                    - field.key, field.value --> are the texts for key and values
                    - field.confidence, field.key.confidence, field.value.confidence
                    - field.id, field.key.id, field.value.id
                    - field.geometry, field.key.geometry, field.value.geometry // send key and values
                    '''
                    return True
        return False