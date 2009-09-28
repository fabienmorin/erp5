##############################################################################
#
# Copyright (c) 2001 Zope Corporation and Contributors. All Rights Reserved.
# Copyright (c) 2002-2004 Nexedi SARL and Contributors. All Rights Reserved.
#                    Jean-Paul Smets-Solanes <jp@nexedi.com>
#
# WARNING: This program as such is intended to be used by professional
# programmers who take the whole responsability of assessing all potential
# consequences resulting from its eventual inadequacies and bugs
# End users who are looking for a ready-to-use solution with commercial
# garantees and support are strongly adviced to contract a Free Software
# Service Company
#
# This software is subject to the provisions of the Zope Public License,
# Version 2.0 (ZPL).  A copy of the ZPL should accompany this distribution.
# THIS SOFTWARE IS PROVIDED "AS IS" AND ANY AND ALL EXPRESS OR IMPLIED
# WARRANTIES ARE DISCLAIMED, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF TITLE, MERCHANTABILITY, AGAINST INFRINGEMENT, AND FITNESS
# FOR A PARTICULAR PURPOSE
#
##############################################################################

from Globals import InitializeClass, DTMLFile
from AccessControl import ClassSecurityInfo, getSecurityManager
from Acquisition import aq_base, aq_inner, aq_parent

import Products
import Products.CMFCore.TypesTool
from Products.CMFCore.TypesTool import TypeInformation
from Products.CMFCore.TypesTool import FactoryTypeInformation
from Products.CMFCore.TypesTool import TypesTool
from Products.CMFCore.interfaces.portal_types import ContentTypeInformation\
                                                as ITypeInformation
from Products.CMFCore.ActionProviderBase import ActionProviderBase
from Products.CMFCore.utils import SimpleItemWithProperties
from Products.CMFCore.Expression import createExprContext, Expression
from Products.CMFCore.exceptions import AccessControl_Unauthorized
from Products.CMFCore.utils import _checkPermission
from Products.ERP5Type import PropertySheet
from Products.ERP5Type import _dtmldir
from Products.ERP5Type import Permissions
from Products.ERP5Type.UnrestrictedMethod import UnrestrictedMethod
from Products.ERP5Type.XMLObject import XMLObject

# Security uses ERP5Security by default
try:
  from Products.ERP5Security import ERP5UserManager
except ImportError:
  ERP5UserManager = None

# If ERP5Security is not installed try NuxUserGroups
if ERP5UserManager is None:
  try:
    from Products import NuxUserGroups
  except ImportError:
    NuxUserGroups = None

from TranslationProviderBase import TranslationProviderBase

from sys import exc_info
from zLOG import LOG, ERROR
from Products.CMFCore.exceptions import zExceptions_Unauthorized

ERP5TYPE_SECURITY_GROUP_ID_GENERATION_SCRIPT = 'ERP5Type_asSecurityGroupId'

class ERP5TypeInformation(XMLObject,
                          FactoryTypeInformation,
                          TranslationProviderBase):
    """
    ERP5 Types are based on FactoryTypeInformation

    The most important feature of ERP5Types is programmable acquisition which
    allows defining attributes which are acquired through categories.

    Another feature is to define the way attributes are stored (localy,
    database, etc.). This allows combining multiple attribute sources
    in a single object. This feature will be in reality implemented
    through PropertySheet classes (TALES expressions)
    """

    portal_type = 'Base Type'
    meta_type = 'ERP5 Base Type'
    isPortalContent = 1
    isRADContent = 1

    security = ClassSecurityInfo()
    security.declareObjectProtected(Permissions.AccessContentsInformation)

    # Declarative properties
    property_sheets = ( PropertySheet.Base
                      , PropertySheet.XMLObject
                      , PropertySheet.SimpleItem
                      , PropertySheet.Folder
                      , PropertySheet.BaseType
                      )

    acquire_local_roles = False
    property_sheet_list = ()
    base_category_list = ()
    init_script = ''
    product = 'ERP5Type'
    hidden_content_type_list = ()
    permission = ''

    def __init__(self, id, **kw):
      XMLObject.__init__(self, id)
      # copied from CMFCore.TypesTool
      if (not kw.has_key('content_meta_type')
          and kw.has_key('meta_type')):
        kw['content_meta_type'] = kw['meta_type']
      if (not kw.has_key('content_icon')
          and kw.has_key('icon')):
        kw['content_icon'] = kw['icon']
      self.__dict__.update(kw)

    # Groups are used to classify portal types (e.g. resource).
    # IMPLEMENTATION NOTE
    # The current implementation is practical but not modular at all
    # Providing extensible document groups will be desirable at some point
    # Implementation could consist for example in allowing to define
    # the list of groups at the level of ERP5Site either
    # with a default value or with a user specified value. Accessors
    # to portal type groups should then be generated dynamically through
    # _aq_dynamic. This would provide limitless group definition.
    # The main issue in providing too much flexibility at this level
    # is to reduce standardisation. New groups should therefore be handled
    # with great care.
    defined_group_list = (
      # Framework
      'alarm', 'rule',
      # ERP5 UBM (5 Classes)
      'resource', 'node', 'item',
      'delivery', 'delivery_movement',
      'order', 'order_movement',
      'container', 'container_line',
      'path',
      # Trade
      'discount', 'payment_condition', 'payment_node',
      'supply', 'supply_path', 'inventory_movement', 'tax_movement',
      # PDM
      'transformation', 'variation', 'sub_variation',
      'product', 'service',
      # Accounting
      'accounting_transaction', 'accounting_movement',
      'invoice', 'invoice_movement', 'balance_transaction_line',
      # CRM
      'event', 'ticket',
      # DMS
      'document', 'web_document', 'file_document',
      'recent_document', 'my_document', 'template_document',
      'crawler_index',
      # MRP
      'divergence_tester', 'calendar_period',
      # Project
      'project',
      # budget
      'budget_variation',
      # Module
      'module',
      # Movement Group
      'movement_group',
    )
    group_list = ()

    #
    #   Acquisition editing interface
    #

    security.declarePrivate('_guessMethodAliases')
    def _guessMethodAliases(self):
        """ Override this method to disable Method Aliases in ERP5.
        """
        self.setMethodAliases({})
        return 1

    #
    #   Agent methods
    #
    def _queryFactoryMethod(self, container, default=None):

        if not self.product or not self.factory or container is None:
            return default

        # In case we aren't wrapped.
        dispatcher = getattr(container, 'manage_addProduct', None)

        if dispatcher is None:
            return default

        try:
            p = dispatcher[self.product]
        except AttributeError:
            LOG('Types Tool', ERROR, '_queryFactoryMethod raised an exception',
                error=exc_info())
            return default

        m = getattr(p, self.factory, None)

        if m is not None:
            try:
                # validate() can either raise Unauthorized or return 0 to
                # mean unauthorized.
                permission = self.permission
                if permission:
                  if _checkPermission(permission, container):
                    return m
                  else:
                    return default
                elif getSecurityManager().validate(p, p, self.factory, m):
                  return m
            except zExceptions_Unauthorized:  # Catch *all* Unauths!
                pass

        return default

    security.declarePublic('constructInstance')
    def constructInstance( self, container, id,
                           created_by_builder=0, *args, **kw ):
        """
        Build a "bare" instance of the appropriate type in
        'container', using 'id' as its id.
        Call the init_script for the portal_type.
        Returns the object.
        """
        # This is part is copied from CMFCore/TypesTool/constructInstance
        # In case of temp object, we don't want to check security
        if (not (hasattr(container, 'isTempObject')
                 and container.isTempObject())
            and not self.isConstructionAllowed(container)):
          raise AccessControl_Unauthorized('Cannot create %s' % self.getId())

        # Then keep on the construction process
        ob = self._constructInstance(container, id, *args, **kw)

        # Portal type has to be set before setting other attributes
        # in order to initialize aq_dynamic
        if hasattr(ob, '_setPortalTypeName'):
          #ob._setPortalTypeName(self.getId())
          # XXX rafael: if we use _set because it is trigger by interaction
          # workflow and it is annoyning without security setted
          ob.portal_type = self.getId()

        # Only try to assign roles to security groups if some roles are defined
        # This is an optimisation to prevent defining local roles on subobjects
        # which acquire their security definition from their parent
        # The downside of this optimisation is that it is not possible to
        # set a local role definition if the local role list is empty
        if self.getRoleList():
          self.updateLocalRolesOnObject(ob)

        # notify workflow after generating local roles, in order to prevent
        # Unauthorized error on transition's condition
        if hasattr(aq_base(ob), 'notifyWorkflowCreated'):
          ob.notifyWorkflowCreated()

        # Reindex the object at the end
        ob.reindexObject()

        init_script = self.getTypeInitScriptId()
        if init_script:
          # Acquire the init script in the context of this object
          kw['created_by_builder'] = created_by_builder
          getattr(ob, init_script)(*args, **kw)

        return ob

    security.declareProtected(Permissions.ManagePortal,
                              'setPropertySheetList')
    def setPropertySheetList(self, property_sheet_list):
      # XXX CMF compatibility
      self._setTypePropertySheetList(property_sheet_list)

    security.declareProtected(Permissions.AccessContentsInformation,
                              'getHiddenContentTypeList')
    def getHiddenContentTypeList(self):
      # XXX CMF compatibility
      return self.getTypeHiddenContentTypeList(())

    security.declareProtected(Permissions.AccessContentsInformation,
                              'getInstanceBaseCategoryList')
    def getInstanceBaseCategoryList(self):
      """ Return all base categories of the portal type """
      # get categories from portal type
      base_category_set = set(self.getTypeBaseCategoryList())

      # get categories from property sheet
      ps_list = [getattr(PropertySheet, p, None)
                 for p in self.getTypePropertySheetList()]
      # from the property sheets defined on the class
      m = Products.ERP5Type._m
      if m.has_key(self.factory):
        klass = m[self.factory].klass
        if klass is not None:
          from Products.ERP5Type.Base import getClassPropertyList
          ps_list += getClassPropertyList(klass)

      # XXX Can't return set to restricted code in Zope 2.8.
      return list(base_category_set.union(category
        for base in ps_list
        for category in getattr(base, '_categories', ())))

    security.declareProtected(Permissions.AccessContentsInformation,
                              'getInstancePropertyMap')
    def getInstancePropertyMap(self):
      """
      Returns the list of properties which are specific to the portal type.

      We do this by creating a temp object at the root of the portal
      and invoking propertyMap
      """
      # Access the factory method for temp object by guessing it
      # according to ERP5 naming conventions (not very nice)
      factory_method_id = self.factory.replace('add', 'newTemp', 1)
      if not factory_method_id.startswith('newTemp'):
        raise
      factory_method = getattr(Products.ERP5Type.Document, factory_method_id)
      id = "some_very_unlikely_temp_object_id_which_should_not_exist"
      portal = self.getPortalObject()
      portal_ids = portal.objectIds()
      while id in portal_ids:
        id = id + "d"
      return factory_method(portal, id).propertyMap()

    security.declarePrivate('updateLocalRolesOnObject')
    def updateLocalRolesOnObject(self, *args, **kw):
      return UnrestrictedMethod(self._updateLocalRolesOnObject)(*args, **kw)

    def _updateLocalRolesOnObject(self, ob, user_name=None, reindex=True):
      """
        Assign Local Roles to Groups on object 'ob', based on Portal Type Role
        Definitions and "ERP5 Role Definition" objects contained inside 'ob'.
      """
      #FIXME We should check the type of the acl_users folder instead of
      #      checking which product is installed.
      if user_name is None:
        # First try to guess from the owner
        try:
          user_name = ob.getOwnerInfo()['id']
        except (AttributeError, TypeError):
          pass
      if user_name is None:
        if ERP5UserManager is not None:
          # We use id for roles in ERP5Security
          user_name = getSecurityManager().getUser().getId()
        elif NuxUserGroups is not None:
          user_name = getSecurityManager().getUser().getUserName()
        else:
          raise RuntimeError, 'Product "ERP5Security" was not found on'\
                'your setup. '\
                'Please install it to benefit from group-based security'

      # Create an empty local Role Definition dict
      role_category_list_dict = {}
      role_group_list_dict = {}

      # Fill it with explicit local roles defined as subobjects of current
      # object
      if getattr(aq_base(ob), 'isPrincipiaFolderish', 0) and \
         self.allowType('Role Definition'):
        for roledef in ob.objectValues(portal_type='Role Definition'):
          if roledef.getRoleName():
            role_category_list_dict.setdefault(roledef.getRoleName(), []).append(
                            {
                                'category_order'  : ['agent'],
                                'agent'           : roledef.getAgentList()
                            })

      # Retrieve and parse applicable roles
      for role in self.getFilteredRoleListFor(ob):
        # For each role definition, we look for the base_category_script
        # and try to use it to retrieve the values for the base_category list
          # get the list of base_categories that are statically defined
          static_base_category_list = [x.split('/', 1)[0]
                                       for x in role.getRoleCategoryList()]
          # get the list of base_categories that are to be fetched through the
          # script
          category_order_list = role.getRoleBaseCategoryList()
          dynamic_base_category_list = [x for x in category_order_list
                                        if x not in static_base_category_list]
          # get the aggregated list of base categories, to preserve the order
          for bc in static_base_category_list:
            if bc not in category_order_list:
              category_order_list.append(bc)

          # get the script and apply it if dynamic_base_category_list is not
          # empty
          if len(dynamic_base_category_list) > 0:
            base_category_script_id = role.getRoleBaseCategoryScriptId()
            base_category_script = getattr(ob, base_category_script_id, None)
            if base_category_script is not None:
              # call the script, which should return either a dict or a list of
              # dicts
              category_result = base_category_script(
                                        dynamic_base_category_list,
                                        user_name,
                                        ob,
                                        ob.getPortalType() )
              # If we decide in the script that we don't want to update the
              # security for this object, we can just have it return None
              # instead of a dict or list of dicts
              if category_result is None:
                continue
            else:
              raise RuntimeError, 'Script %s was not found to fetch values for'\
                      ' base categories : %s' % (base_category_script_id,
                                            ', '.join(dynamic_base_category_list))
          else:
            # no base_category needs to be retrieved using the script, we use
            # a list containing an empty dict to trick the system into
            # creating one category_value_dict (which will only use statically
            # defined categories)
            category_result = [{}]

          # Prepare definition dict once only
          category_definition_dict = {}
          for c in role.getRoleCategoryList():
            bc, value = c.split('/', 1)
            category_definition_dict.setdefault(bc, []).append(value)
          # Now create role dict for each roles
          for role in role.getRoleNameList():
            if isinstance(category_result, dict):
              # category_result is a dict (which provide group IDs directly)
              # which represents of mapping of roles, security group IDs
              # XXX explain that this is for providing user IDs mostly
              role_group_list = role_group_list_dict.setdefault(role, [])
              for k, v in category_result.items():
                if k == role:
                  role_group_list.extend(v)
            else:
              # category_result is a list of dicts that represents the resolved
              # categories we create a category_value_dict from each of these
              # dicts aggregated with category_order and statically defined
              # categories
              role_category_list = role_category_list_dict.setdefault(role, [])
              for category_dict in category_result:
                category_value_dict = {'category_order':category_order_list}
                category_value_dict.update(category_dict)
                category_value_dict.update(category_definition_dict)
                role_category_list.append(category_value_dict)

      # Generate security group ids from category_value_dicts
      role_group_id_dict = {}
      parent = ob.aq_parent
      group_id_generator = getattr( parent,
                             ERP5TYPE_SECURITY_GROUP_ID_GENERATION_SCRIPT,
                             None )
      group_id_generator = group_id_generator.__of__(ob)
      if group_id_generator is None:
        raise RuntimeError, '%s script was not found' % \
                              ERP5TYPE_SECURITY_GROUP_ID_GENERATION_SCRIPT
      for role, group_list in role_group_list_dict.items():
        role_group_id_dict.setdefault(role, []).extend(group_list)
      for role, value_list in role_category_list_dict.items():
        role_group_dict = {}
        for category_dict in value_list:
          group_id = group_id_generator(**category_dict) # category_order is passed in the dict
          # If group_id is not defined, do not use it
          if group_id not in (None, ''):
            if isinstance(group_id, str):
              # Single group is defined (this is usually for group membership)
              # DEPRECATED due to cartesian product requirement
              role_group_dict[group_id] = 1
            else:
              # Multiple groups are defined (list of users
              # or list of group IDs resulting from a cartesian product)
              for user_id in group_id:
                role_group_dict[user_id] = 1
        role_group_id_dict.setdefault(role, []).extend(role_group_dict.keys())

      # Switch index from role to group id
      group_id_role_dict = {}
      for role, group_list in role_group_id_dict.items():
        for group_id in group_list:
          group_id_role_dict.setdefault(group_id, []).append(role)

      # Update role assignments to groups
      if ERP5UserManager is not None: # Default implementation
        # Clean old group roles
        old_group_list = ob.get_local_roles()
        ob.manage_delLocalRoles([x[0] for x in old_group_list])
        # Save the owner
        for group, role_list in old_group_list:
          if 'Owner' in role_list:
            if not group_id_role_dict.has_key(group):
              group_id_role_dict[group] = ('Owner',)
            else:
              group_id_role_dict[group].append('Owner')
        # Assign new roles
        for group, role_list in group_id_role_dict.items():
          ob.manage_addLocalRoles(group, role_list)
      else: # NuxUserGroups implementation
        # Clean old group roles
        old_group_list = ob.get_local_group_roles()
        # We duplicate role settings to mimic PAS
        ob.manage_delLocalGroupRoles([x[0] for x in old_group_list])
        ob.manage_delLocalRoles([x[0] for x in old_group_list])
        # Save the owner
        for group, role_list in old_group_list:
          if 'Owner' in role_list:
            if not group_id_role_dict.has_key(group):
              group_id_role_dict[group] = ('Owner',)
            else:
              group_id_role_dict[group].append('Owner')
        # Assign new roles
        for group, role_list in group_id_role_dict.items():
          # We duplicate role settings to mimic PAS
          ob.manage_addLocalGroupRoles(group, role_list)
          ob.manage_addLocalRoles(group, role_list)
      # Make sure that the object is reindexed
      if reindex:
        ob.reindexObjectSecurity()

    security.declarePrivate('getFilteredRoleListFor')
    def getFilteredRoleListFor(self, ob=None):
        """Return all roles applicable to the object against user."""
        portal = self.portal_url.getPortalObject()
        if ob is None:
          folder = portal
        else:
          folder = aq_parent(ob)
          # Search up the containment hierarchy until we find an
          # object that claims it's a folder.
          while folder is not None:
            if getattr(aq_base(folder), 'isPrincipiaFolderish', 0):
              # found it.
              break
            else:
              folder = aq_parent(folder)

        ec = createExprContext(folder, portal, ob)
        return (role for role in self.getRoleList() if role.testCondition(ec))

    security.declareProtected(Permissions.ManagePortal, 'updateRoleMapping')
    def updateRoleMapping(self, REQUEST=None, form_id=''):
      """Update the local roles in existing objects.
         XXX This should be implemented the same way as
             ERP5Site_checkCatalogTable (cf erp5_administration).
      """
      portal = self.getPortalObject()
      update_role_tag = self.__class__.__name__ + ".updateRoleMapping"

      object_list = [x.path for x in
                     portal.portal_catalog(portal_type=self.id, limit=None)]
      object_list_len = len(object_list)
      # We need to use activities in order to make sure it will
      # work for an important number of objects
      activate = portal.portal_activities.activate
      for i in xrange(0, object_list_len, 100):
        current_path_list = object_list[i:i+100]
        activate(activity='SQLQueue', priority=3, tag=update_role_tag) \
        .callMethodOnObjectList(current_path_list,
                                'updateLocalRolesOnSecurityGroups',
                                reindex=False)
        activate(activity='SQLQueue', priority=3, after_tag=update_role_tag) \
        .callMethodOnObjectList(current_path_list,
                                'reindexObjectSecurity')

      if REQUEST is not None:
        message = '%d objects updated' % object_list_len
        return REQUEST.RESPONSE.redirect('%s/%s?portal_status_message=%s'
          % (self.absolute_url_path(), form_id, message))

    #
    #   Helper methods
    #
    def manage_editProperties(self, REQUEST):
      """
        Method overload

        Reset _aq_dynamic if property_sheet definition has changed)

        XXX This is only good in single thread mode.
            In ZEO environment, we should call portal_activities
            in order to implement a broadcast update
            on production hosts
      """
      previous_property_sheet_list = self.property_sheet_list
      base_category_list = self.base_category_list
      result = FactoryTypeInformation.manage_editProperties(self, REQUEST)
      if previous_property_sheet_list != self.property_sheet_list or \
                   base_category_list != self.base_category_list:
        from Products.ERP5Type.Base import _aq_reset
        _aq_reset()
      return result

    security.declareProtected(Permissions.AccessContentsInformation,
                              'PrincipiaSearchSource')
    def PrincipiaSearchSource(self):
      # Support for "Find" tab in ZMI
      search_source_list = [self.getId(),
                            self.getTypeFactoryMethodId(),
                            self.getTypeAddPermission(),
                            self.getTypeInitScriptId()]
      search_source_list += self.getTypePropertySheetList(())
      search_source_list += self.getTypeBaseCategoryList(())
      return ' '.join(filter(None, search_source_list))

    #
    # USE_BASE_TYPE
    #

    security.declarePrivate('getRoleList')
    def getRoleList(self):
      """Return all roles for this portal type"""
      return self.objectValues(portal_type='Role Information')

    security.declarePrivate('getActionList')
    def getActionList(self):
      """Return all actions for this portal type"""
      return self.objectValues(portal_type='Action Information')

    def getIcon(self):
      return self.content_icon

    def getTypeInfo(self, *args):
      if not args:
        return XMLObject.getTypeInfo(self)
      else:
        return self.getParentValue().getTypeInfo(self, *args)

    security.declareProtected(Permissions.AccessContentsInformation,
                              'getAvailablePropertySheetList')
    def getAvailablePropertySheetList(self):
      return sorted(k for k in Products.ERP5Type.PropertySheet.__dict__
                      if not k.startswith('__'))

    security.declareProtected(Permissions.AccessContentsInformation,
                              'getAvailableConstraintList')
    def getAvailableConstraintList(self):
      return sorted(k for k in Products.ERP5Type.Constraint.__dict__
                      if k != 'Constraint' and not k.startswith('__'))

    security.declareProtected(Permissions.AccessContentsInformation,
                              'getAvailableGroupList')
    def getAvailableGroupList(self):
      return sorted(self.defined_group_list)

    security.declareProtected(Permissions.AccessContentsInformation,
                              'getAvailableBaseCategoryList')
    def getAvailableBaseCategoryList(self):
        return sorted(self._getCategoryTool().getBaseCategoryList())

    #
    # Compatibitility code for actions
    #

    security.declarePrivate('listActions')
    def listActions(self, info=None, object=None):
      """ List all the actions defined by a provider."""
      return sorted(self.getActionList(), key=lambda x: x.getFloatIndex())

    def _importOldAction(self, old_action):
      from Products.ERP5Type.Document.ActionInformation import ActionInformation
      old_action = old_action.__getstate__()
      action_type = old_action.pop('category', None)
      action = ActionInformation(self.generateNewId())
      for k, v in old_action.iteritems():
        if k in ('action', 'condition', 'icon'):
          if not v:
            continue
          v = v.__class__(v.text)
        setattr(action, {'id': 'reference',
                         'priority': 'float_index',
                        }.get(k, k), v)
      action.uid = None
      action = self[self._setObject(action.id, action, set_owner=0)]
      if action_type:
        action._setCategoryMembership('action_type', action_type)
      return action

    def _exportOldAction(self, action):
      from Products.CMFCore.ActionInformation import ActionInformation
      old_action = ActionInformation(action.reference,
        category=action.getActionType(),
        # We don't have the same default values for the following properties:
        priority=action.getFloatIndex(),
        permissions=tuple(action.getActionPermissionList()))
      for k, v in action.__dict__.iteritems():
        if k in ('action', 'condition', 'icon'):
          v = v.__class__(v.text)
        elif k in ('id', 'float_index', 'permissions', 'reference'):
          continue
        setattr(old_action, k, v)
      return old_action

    def _importRole(self, role_property_dict):
      from Products.ERP5Type.Document.RoleInformation import RoleInformation
      role = RoleInformation(self.generateNewId())
      for k, v in role_property_dict.iteritems():
        if k == 'condition':
          if isinstance(v, Expression):
            v = v.text
          if not v:
            continue
          v = Expression(v)
        elif k == 'priority':
          continue
        elif k == 'id':
          k, v = 'role_name', tuple(x.strip() for x in v.split(';'))
        elif k in ('base_category', 'category'):
          k, v = 'role_' + k, tuple(x.strip() for x in v)
        elif k == 'base_category_script':
          k = 'role_base_category_script_id'
        setattr(role, k, v)
      role.uid = None
      return self[self._setObject(role.id, role, set_owner=0)]


InitializeClass( ERP5TypeInformation )
