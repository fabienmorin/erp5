##############################################################################
#
# Copyright (c) 2002 Nexedi SARL and Contributors. All Rights Reserved.
#                    Jean-Paul Smets-Solanes <jp@nexedi.com>
#
# WARNING: This program as such is intended to be used by professional
# programmers who take the whole responsability of assessing all potential
# consequences resulting from its eventual inadequacies and bugs
# End users who are looking for a ready-to-use solution with commercial
# garantees and support are strongly adviced to contract a Free Software
# Service Company
#
# This program is Free Software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
#
##############################################################################

from Globals import InitializeClass, PersistentMapping
from Acquisition import aq_base, aq_parent, aq_inner, aq_acquire
from AccessControl import ClassSecurityInfo
from Products.ERP5Type import Permissions
from Products.ERP5Type.Document.Folder import Folder
from Products.ERP5Type.Utils import cartesianProduct
from Products.ERP5Type.Base import TempBase

from zLOG import LOG
from string import join, replace

class XMLMatrix(Folder):
    """
        A mix-in class which provides a matrix like
        access to objects. Matrices are of any dimension

        We still must make XMLMatrix a subclass of Base so
        that we can inherit from ExtensionClass.Base
        which is required for multiple inheritance to work
        as expected. Read this for more information:

        http://www.daa.com.au/pipermail/pygtk/2001-May/001180.html

        In our case, we will use Folder because we want to inherit
        from Folder consistency checking

    """

    # Declarative security
    security = ClassSecurityInfo()

    # Matrix Methods
    security.declareProtected( Permissions.View, 'getCell' )
    def getCell(self, *kw , **kwd):
      """
          Access a cell at row and column
      """
      if not hasattr(self, 'index'):
        return None

      base_id = kwd.get('base_id', 'cell')
      if not self.index.has_key(base_id):
        return None
        
      cell_id_list = [base_id]
      append = cell_id_list.append
      index = self.index[base_id]
      for i, my_id in enumerate(kw):
        try:
          append(str(index[i][my_id]))
        except KeyError:
          return None
      cell_id = '_'.join(cell_id_list)
      return self.get(cell_id)

    security.declareProtected( Permissions.View, 'getCellProperty' )
    def getCellProperty(self, *kw , **kwd):
      """
          Get a property of a cell at row and column
      """
      cell = self.getCell(*kw, **kwd)
      if cell is None:
        return None
        
      base_id = kwd.get('base_id', 'cell')
      return cell.getProperty(base_id)
      
    security.declareProtected( Permissions.View, 'hasCell' )
    def hasCell(self, *kw , **kwd):
      """
          Checks if cell exists
      """
      if not hasattr(self, 'index'):
        return 0

      base_id = kwd.get('base_id', 'cell')
      cell_id = base_id
      if not self.index.has_key(cell_id):
        return 0

      i = 0
      for my_id in kw:
        if self.index[base_id].has_key(i):
          if self.index[base_id][i].has_key(my_id):
            cell_id += '_%s' % self.index[base_id][i][my_id]
          else:
            return 0
        else:
          return 0
        i += 1

      return self.get(cell_id) is not None

    security.declareProtected( Permissions.ModifyPortalContent, 'hasCellContent' )
    def hasCellContent(self, base_id='cell'):
      """
          This method can be hasCellContent
      """
      aq_self = aq_base(self)

      if not hasattr(self, 'index'):
        return 0

      if not self.index.has_key(base_id):
        return 0

      for i in self.getCellIds(base_id=base_id):
        if hasattr(self, i): # We should try to use aq_self if possible but XXX
          return 1

      return 0

    security.declareProtected( Permissions.View, 'hasInRange' )
    def hasInRange(self, *kw , **kwd):
      """
          Checks if cell exists
      """
      if not hasattr(self, 'index'):
        return 0

      base_id = kwd.get('base_id', 'cell')
      cell_id = base_id
      if not self.index.has_key(cell_id):
        return 0

      i = 0
      for my_id in kw:
        if self.index[base_id].has_key(i):
          if self.index[base_id][i].has_key(my_id):
            cell_id += '_%s' % self.index[base_id][i][my_id]
          else:
            return 0
        else:
          return 0
        i += 1

      return 1

    security.declareProtected( Permissions.ModifyPortalContent, '_setCellRange' )
    def _setCellRange(self, *kw, **kwd):
      """
          Set a new range for a matrix, this method can
          also handle a changement of the size of a matrix
      """
      base_id = kwd.get('base_id', 'cell')

      movement = {}  # We will put in this dictionnary the previous and new
                     # id of a given cell
      new_index = PersistentMapping() # new_index defines the relation between keys
                                      # and ids of cells

      if not hasattr(aq_base(self), 'index'):
        self.index = PersistentMapping()

      # Return if previous range is the same
      current_range = self.getCellRange(base_id=base_id)
      if current_range == list(kw): # kw is a tuple
        LOG('XMLMatrix',0,'return form _setCellRange - no need to change range')
        return

      # We must make sure the base_id exists
      # in the event of a matrix creation for example
      if not self.index.has_key(base_id):
        # Create an index for this base_id
        self.index[base_id] = PersistentMapping()

      new_index[base_id]=PersistentMapping() # fixed by JPS
      # Recreate a new index for the new range defined in *kw
      i = 0
      for index_ids in kw:
        new_index[base_id][i] = PersistentMapping() #  fixed by JPS ({})
        j = 0
        for my_id in index_ids:
          new_index[base_id][i][my_id] = j
          j += 1
        i += 1

      # Create the movement dictionnary
      movement[base_id]={}
      # Look at each dimension i of the previous index
      for i in self.index[base_id].keys():
        movement[base_id][i]={}
        # Look at each index in a given dimension i
        for my_id in self.index[base_id][i].keys():
          # If the new index has the same dimensionality
          # Look at new location of cells
          if new_index[base_id].has_key(i):
            new_place=None
            old_place = self.index[base_id][i][my_id]
            if my_id in new_index[base_id][i].keys():
              # if my_id still exists in the new_index
              new_place = new_index[base_id][i][my_id]
            # create a movement in dimension i between old_place and new_place
            movement[base_id][i][old_place] = new_place

      # Rename every 'object_name' by 'temp_object_name'
      object_id_list = []
      for object in self.objectValues():
        if object.id.find(base_id) == 0:
          # We want to make sure we have only base_id, ex: foo_0_0 and not foo_bar_0_0
          if (object.id) > len(base_id):
            try:
              int(object.id[len(base_id)+1:].split('_')[0])
              test = self._getOb(object.id) # If the object was created during this transaction,
                                            # then we do not need to work on it
              object_id_list += [object.id]
            except ValueError, KeyError:
              pass

      for object_id in object_id_list:
        new_name = 'temp_' + object_id
        object = self._getOb(object_id)
        object.isIndexable = 0 # block reindexing at this time
        object.id = new_name
        #LOG("Set Object",0, str(new_name))
        self._setObject(new_name, object)
        #LOG("Del Object",0, str(object_id))
        self._delObject(object_id)

      for object_id in object_id_list:
        # Retrieve the place of the object, for movement_0_0 it is ['0','0']
        object_place = object_id[len(base_id)+1:].split('_')
        to_delete = 1
        # We must have the same number of dimensions
        if len(object_place) == len(new_index[base_id]):
          # Let us browse each dimension of the previous index
          for i in range(len(object_place)):
            # Build each part of the nex id by looking up int. values
            old_place = int(object_place[i])
            # We are looking inside the movement dictionnary where
            # we should move the object, so for example
            # 'qantity_2_5' is renamed as 'quantity_4_3'
            if movement[base_id].has_key(i):
              if movement[base_id][i].has_key(old_place):
                # Replace the place of the cell only if there where a change
                if (movement[base_id][i][old_place]) != None:
                  object_place[i] = str(movement[base_id][i][old_place])
                  to_delete = 0
                else:
                  object_place[i] = None

            # XXX In this case, we delete every cell wich are not in the
            # movement dictionnary, may be this is very bad, so may be
            # we need to add an extra check here, ie if
            # if movement[base_id][i].has_key(old_place) returns None,
            # We may want to keep the cell, but only if we are sure
            # the movement dictionnary will not define a new cell with this id

        new_object_id_list = []

        if not to_delete and not (None in object_place):
          o = self._getOb('temp_' + object_id)
          new_name = base_id + '_' + join(object_place,'_')
          o.id = new_name
          new_object_id_list.extend(new_name)
          #LOG("Set2 Object",0, str(new_name))
          self._setObject(new_name,o)
          #LOG("Del2 Object",0, 'temp_' + str(object_id))
          self._delObject('temp_' + object_id) # In all cases, we have to remove the temp object
          o.isIndexable = 1 # reindexing is possible again
          if new_name != object_id:
            # Theses two lines are very important, if the object is renamed
            # then we must uncatalog the previous one
            o.unindexObject(path='%s/%s' % (self.getUrl() , object_id))
          o.reindexObject() # we reindex in case position has changed - uid should be consistent
          LOG('XMLMatrix', 0, 'reindex object uid %s' % repr(o.getUid()))
        else:
          o = self._getOb('temp_' + object_id)
          # In all cases, we have to remove the temp object
          LOG("Del2 Object",0, 'temp_' + str(object_id))
          LOG("Del2 Object",0, str(o.uid))
          #ATTENTION -> if path is not good, it will not be able to uncatalog !!!!!!!
          #o.immediateReindexObject() # STILL A PROBLEM -> getUidForPath XXXXXXXXXXx
          if object_id not in new_object_id_list: # do not unindex a new object
            o.isIndexable = 1
            o.unindexObject(path='%s/%s' % (self.getUrl() , object_id))
            o.isIndexable = 0 # unindexed already forced
          self._delObject('temp_' + object_id) # object will be removed from catalog automaticaly

      # We don't need the old index any more, we
      # can set the new index
      self.index[base_id] = new_index[base_id]    # pb, KeyError, variation, car passage
        # de coloris, taille ?seulement taille
      #LOG("The End",0, '')

    security.declareProtected( Permissions.ModifyPortalContent, 'setCellRange' )
    def setCellRange(self, *kw, **kwd):
      """
          Define the indices provided
          one list per index (kw)

          Any number of list can be provided
      """
      self._setCellRange(*kw, **kwd)
      self.reindexObject()

    security.declareProtected(Permissions.ModifyPortalContent, 
                              'updateCellRange')
    def updateCellRange(self, base_id,script_id=None):
      """
        The asCellRange script if PT dependent
        whoch is not the case with this kind of code
        a better implementation consists in defining asCellRange as a 
        generic method at matrix level (OverridableMethod(portal_type))
        which lookuops for scipt in class, meta_type and PT form 
        interaction could be implemented with interaction workflow
        this method should be renamed updateCellRange or updateMatrixCellRange
        base_id is parameter of updateCellRange
        
        asCellRange scripts should be unified if possible
      """
      script_name_end = '_asCellRange'
      if script_id is not None:
        script = getattr(self, script_id)
      else:
        for script_name_begin in [self.getPortalType(), self.getMetaType(), 
                                  self.__class__.__name__]:
          script_name = join([replace(script_name_begin, ' ', ''), 
                              script_name_end], '')
          if hasattr(self, script_name):
            script = getattr(self, script_name)
            break
      try:
        cell_range = script(base_id=base_id,matrixbox=0)
      except UnboundLocalError:
        raise UnboundLocalError,\
              "Did not find cell range script for portal type: %r" %\
              self.getPortalType()
      self.setCellRange(base_id=base_id, *cell_range)


    security.declareProtected( Permissions.ModifyPortalContent, '_renameCellRange' )
    def _renameCellRange(self, *kw, **kwd):
      """
          Rename a range for a matrix, this method can
          also handle a changement of the size of a matrix
      """
      base_id = kwd.get('base_id', 'cell')

      movement = {}  # We will put in this dictionnary the previous and new
                     # id of a given cell
      new_index = PersistentMapping() # new_index defines the relation between keys
                                      # and ids of cells

      if not hasattr(self, 'index'):
        self.index = PersistentMapping()

      # Return if previous range is the same
      current_range = self.getCellRange(base_id=base_id) or []
      if current_range == list(kw): # kw is a tuple
        LOG('XMLMatrix',0,'return form _setCellRange - no need to change range')
        return

      # We must make sure the base_id exists
      # in the event of a matrix creation for example
      if not self.index.has_key(base_id):
        # Create an index for this base_id
        self.index[base_id] = PersistentMapping()

      # First, delete all cells which are out of range.
      size_list = []
      for place_list in kw:
        size_list.append(len(place_list))
      if len(kw) < len(current_range):
        size_list.extend([1] * (len(current_range) - len(kw)))
      removed_cell_id_list = []
      cell_id_list = []
      for cell_id in self.getCellIdList(base_id = base_id):
        if self.get(cell_id) is not None:
          cell_id_list.append(cell_id)
      for cell_id in cell_id_list:
        index_list = []
        for index in cell_id[len(base_id)+1:].split('_'):
          index_list.append(int(index))
        for i in range(len(index_list)):
          if index_list[i] >= size_list[i]:
            removed_cell_id_list.append(cell_id)
            break
      for cell_id in removed_cell_id_list:
        self._delObject(cell_id)
        cell_id_list.remove(cell_id)

      # Secondly, rename coordinates. This does not change cell ids.
      for i in range(max(len(kw), len(current_range))):
        if i >= len(kw):
          del self.index[base_id][i]
        else:
          if i >= len(current_range):
            self.index[base_id][i] = PersistentMapping()
          for place in self.index[base_id][i].keys():
            if place not in kw[i]:
              del self.index[base_id][i][place]
          j = 0
          for place in kw[i]:
            self.index[base_id][i][place] = j
            j += 1

      # Lastly, rename ids and catalog/uncatalog everything.
      if len(current_range) < len(kw):
        # Need to move, say, base_1_2 -> base_1_2_0
        appended_id = '_0' * (len(kw) - len(current_range))
        for old_id in cell_id_list:
          cell = self.get(old_id)
          if cell is not None:
            new_id = old_id + appended_id
            cell.isIndexable = 0
            cell.id = new_id
            self._setObject(new_id, cell)
            self._delObject(old_id)
            cell.isIndexable = 1
            cell.reindexObject()
            #cell.unindexObject(path='%s/%s' % (self.getUrl(), old_id))
      elif len(current_range) > len(kw):
        # Need to move, say, base_1_2_0 -> base_1_2
        removed_id_len = 2 * (len(current_range) - len(kw))
        for old_id in cell_id_list:
          cell = self.get(old_id)
          if cell is not None:
            new_id = old_id[:-removed_id_len]
            cell.isIndexable = 0
            cell.id = new_id
            self._setObject(new_id, cell)
            self._delObject(old_id)
            cell.isIndexable = 1
            cell.reindexObject()
            #cell.unindexObject(path='%s/%s' % (self.getUrl(), old_id))

    security.declareProtected( Permissions.ModifyPortalContent, 'renameCellRange' )
    def renameCellRange(self, *kw, **kwd):
      """
          Rename the indices provided
          one list per index (kw)

          Any number of list can be provided
      """
      self._renameCellRange(*kw, **kwd)
      self.reindexObject()

    security.declareProtected( Permissions.AccessContentsInformation, 'getCellRange' )
    def getCellRange(self, base_id='cell'):
      """
          Returns the cell range as a list of index ids
      """
      if not hasattr(self, 'index'):
        self.index = PersistentMapping()
      cell_range = self.index.get(base_id, None)
      if cell_range is None: return None
      result = []
      for i in range(0,len(cell_range.keys())):
        result_items = cell_range[i].items()
        result_items.sort(lambda x, y: x[1]-y[1])
        result_items = map(lambda x:x[0], result_items)
        result += [result_items]
      return result

    security.declareProtected( Permissions.ModifyPortalContent, 'newCell' )
    def newCell(self, *kw, **kwd):
      """
          This method creates a new cell
      """
      if not hasattr(self, 'index'):
        return None

      base_id = kwd.get('base_id', 'cell')
      cell_id = base_id
      if not self.index.has_key(cell_id):
        return None

      i = 0
      for my_id in kw:
        if self.index[base_id][i].has_key(my_id):
          cell_id += '_%s' % self.index[base_id][i][my_id]
          i += 1
        else:
          raise KeyError, 'Invalid key: %s' % str(kw) # Is this temp ? XXX
          return None
      cell = self.get(cell_id)
      if cell is not None:
        return cell
      else:
        return self.newCellContent(cell_id,**kwd)

    security.declareProtected( Permissions.ModifyPortalContent, 'newCellContent' )
    def newCellContent(self, id,**kw):
      """
          This method can be overriden
      """
      if kw.has_key('portal_type'):
        type_name = kw['portal_type']
      else:
        content_types = self.allowedContentTypes()
        if len(content_types) >= 1:
          type_name = content_types[0].id
        else:
          type_name = self.portal_type
      self.invokeFactory(type_name=type_name,id=id)
      return self.get(id)

    security.declareProtected( Permissions.AccessContentsInformation, 'getCellKeyList' )
    def getCellKeyList(self, base_id = 'cell'):
      """
        Returns a list of possible keys as tuples
      """
      if not hasattr(self, 'index'):
        return ()
      if not self.index.has_key(base_id):
        return ()
      index = self.index[base_id]
      id_tuple = []
      append = id_tuple.append
      for i in xrange(0, len(index)):
        t = index[i]
        append(t.keys())
      if len(id_tuple) == 0:
        return ()
      return cartesianProduct(id_tuple)

    security.declareProtected( Permissions.AccessContentsInformation, 'getCellKeys' )
    getCellKeys = getCellKeyList

    # We should differenciate in future existing tuples from possible tuples
    security.declareProtected( Permissions.AccessContentsInformation, 'getCellRangeKeyList' )
    getCellRangeKeyList = getCellKeyList

    security.declareProtected( Permissions.AccessContentsInformation, 'keyToId' )
    def keyToId(self, kw, base_id = 'cell'):
      """
        Converts a key into an id
      """
      index = self.index[base_id]
      cell_id_list = [base_id]
      append = cell_id_list.append
      for i in xrange(len(kw)):
        try:
          append(str(index[i][kw[i]]))
        except KeyError:
          return None
      return '_'.join(cell_id_list)

    security.declareProtected( Permissions.AccessContentsInformation, 'getCellIdList' )
    def getCellIdList(self, base_id = 'cell'):
      """
        Returns a list of possible keys as tuples
      """
      if not hasattr(self, 'index'):
        return ()
      if not self.index.has_key(base_id):
        return ()
      result = []
      append = result.append
      for kw in self.getCellKeys(base_id = base_id):
        cell_id = self.keyToId(kw, base_id = base_id )
        if cell_id is not None:
          append(cell_id)

      return result

    security.declareProtected( Permissions.AccessContentsInformation, 'getCellIds' )
    getCellIds = getCellIdList

    security.declareProtected( Permissions.AccessContentsInformation, 'cellIds' )
    cellIds = getCellIdList

    # We should differenciate in future all possible ids for existing ids
    security.declareProtected( Permissions.AccessContentsInformation, 'getCellRangeIdList' )
    getCellRangeIdList = getCellIdList

    security.declareProtected( Permissions.AccessContentsInformation, 'getCellValueList' )
    def getCellValueList(self, base_id = 'cell'):
      """
        Returns a list of possible keys as tuples
      """
      result = []
      for id in self.getCellIdList(base_id=base_id):
        o = self.get(id)
        if o is not None:
          result += [o]
      return result

    security.declareProtected( Permissions.AccessContentsInformation, 'cellValues' )
    cellValues = getCellValueList

    security.declareProtected( Permissions.AccessContentsInformation, 'getMatrixList' )
    def getMatrixList(self, base_id = 'cell'):
      """
        Return possible base_id values
      """
      if not hasattr(self, 'index'):
        return ()
      return self.index.keys()
    
    security.declareProtected( Permissions.ModifyPortalContent, 'delMatrix' )
    def delMatrix(self, base_id = 'cell'):
      """
        Delete all cells for a given base_id
        
        XXX BAD NAME: make a difference between deleting matrix and matrix cells
      """
      ids = self.getCellIds(base_id = base_id)
      my_ids = []
      for i in self.objectIds():
        if i in ids:
          my_ids += [i]

      if len(my_ids) > 0:
        self.manage_delObjects(ids=my_ids)

    security.declareProtected( Permissions.AccessContentsInformation, 'delCells' )
    delCells = delMatrix

    security.declareProtected( Permissions.AccessContentsInformation, '_checkConsistency' )
    def _checkConsistency(self, fixit = 0):
      # Check useless cells
      to_delete = []
      errors = []

      # We make sure first that there is an index
      if not hasattr(self, 'index'):
        self.index = PersistentMapping()

      # We will check each cell of the matrix the matrix
      for object in self.objectValues():
        # obect.id is equal to something like 'something_quantity_3_2'
        # So we need to check for every object.id if the value
        # looks like good or not. We split the name
        # check each key in index
        # First we make sure this is a cell
        object_id_split = object.id.split('_')
        # We try to find the first split id which is an int
        base_id_len = len(object_id_split)
        is_int = 1
        test_num = None
        while base_id_len > 0:
          try:
            # if this succeeds, it is very likely a cell with an id such as quantity_X_Y_0_Z
            test_num = int(object_id_split[base_id_len-1])
          except:
            is_int = 0
          if not is_int: break
          base_id_len -= 1
        if base_id_len > 0:
          base_id = '_'.join(object_id_split[0:base_id_len])
        else:
          test_num = None
        if test_num is not None:
            if not self.index.has_key(base_id):
              # The matrix does not have this base_id
              error_message = "There is no index for base_id %s" % base_id
              if fixit: error_message += ' (fixed)'
              errors += [(self.getRelativeUrl(), 'XMLMatrix inconsistency',102,error_message)]
              if object.id not in to_delete:
                to_delete += [object.id]
            else:
              # Check empty indices.
              empty_list = []
              for i in self.index[base_id].keys():
                if self.index[base_id][i] is None or len(self.index[base_id][i]) == 0:
                  error_message = "There is no id for the %dth axis of base_id %s" % (i, base_id)
                  if fixit: error_message += ' (fixed)'
                  errors += [(self.getRelativeUrl(), 'XMLMatrix inconsistency',102,error_message)]
                  empty_list.append(i)
              if fixit:
                for i in empty_list:
                  del self.index[base_id][i]

              len_id = len(self.index[base_id])
              if len(object_id_split) != (len_id + base_id_len): # +1 for the quantity
                error_message = "Dimension of cell is %s but should be %s" % (len(object_id_split)
                                                                            - base_id_len, len_id)
                if fixit: error_message += ' (fixed)'
                errors += [(self.getRelativeUrl(), 'XMLMatrix inconsistency',102,error_message)]
                if object.id not in to_delete:
                  to_delete += [object.id]
              else :
                for i in range(len_id):
                  if int(object_id_split[i+base_id_len]) >= len(self.index[base_id][i]):
                    error_message = "Cell %s is out of bound" % object.id
                    if fixit: error_message += ' (fixed)'
                    errors += [(self.getRelativeUrl(), 'XMLMatrix inconsistency',102,error_message)]
                    if object.id not in to_delete:
                      to_delete += [object.id]

      if fixit and len(to_delete) > 0:
        self.manage_delObjects(to_delete)

      return errors

    security.declareProtected( Permissions.ModifyPortalContent, 'notifyAfterUpdateRelatedContent' )
    def notifyAfterUpdateRelatedContent(self, previous_category_url, new_category_url):
      """
          We must do some matrix range update in the event matrix range 
          is defined by a category
      """
      LOG('XMLMatrix notifyAfterUpdateRelatedContent', 0, str(new_category_url))
      update_method = self.portal_categories.updateRelatedCategory
      for base_id in self.getMatrixList():
        cell_range = self.getCellRange(base_id=base_id)
        new_cell_range = []
        for range_item_list in cell_range:
          new_range_item_list = map(lambda c: update_method(c, previous_category_url, new_category_url), range_item_list)
          new_cell_range.append(new_range_item_list) 
        kwd = {'base_id': base_id}
        LOG('XMLMatrix notifyAfterUpdateRelatedContent matrix', 0, str(base_id))
        LOG('XMLMatrix notifyAfterUpdateRelatedContent _renameCellRange', 0, str(new_cell_range))
        self._renameCellRange(*new_cell_range,**kwd)

class TempXMLMatrix(XMLMatrix):
  """
    If we need Base services (categories, edit, etc) in temporary objects
    we shoud used TempBase
  """
  isIndexable = 0

  def newCellContent(self, id):
    """
          This method can be overriden
    """
    new_temp_object = TempBase(id)
    self._setObject(id, new_temp_object)
    return self.get(id)

  def reindexObject(self, *args, **kw):
    pass

  def unindexObject(self, *args, **kw):
    pass

  def activate(self):
    return self

InitializeClass(XMLMatrix)
