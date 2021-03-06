##############################################################################
#
# Copyright (c) 2002, 2005 Nexedi SARL and Contributors. All Rights Reserved.
#                    Jean-Paul Smets-Solanes <jp@nexedi.com>
#                    Sebastien Robin <seb@nexedi.com>
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

from collections import defaultdict
from AccessControl import ClassSecurityInfo
from Products.ERP5Type.Globals import InitializeClass, DTMLFile
from Products.ERP5Type import Permissions
from Products.ERP5 import _dtmldir
from Products.ERP5Type.Tool.BaseTool import BaseTool
from Products.ZSQLCatalog.SQLCatalog import SQLQuery, Query, ComplexQuery
from zLOG import LOG
from DateTime import DateTime

_MARKER = []

class DomainTool(BaseTool):
    """
        A tool to define reusable ranges and subranges through
        predicate trees
    """
    id = 'portal_domains'
    meta_type = 'ERP5 Domain Tool'
    portal_type     = 'Domain Tool'
    allowed_types   = ('ERP5 Domain', )

    # Declarative Security
    security = ClassSecurityInfo()

    security.declareProtected(Permissions.ManagePortal, 'manage_overview')
    manage_overview = DTMLFile('explainDomainTool', _dtmldir)

    # XXX FIXME method should not be public
    # (some users are not able to see resource's price)
    security.declarePublic('searchPredicateList')
    def searchPredicateList(self, *args, **kw):
      return self._searchPredicateList(restricted=True, *args, **kw)

    def _searchPredicateList(self, context, test=1, sort_method=None,
                             ignored_category_list=None,
                             tested_base_category_list=None,
                             filter_method=None, acquired=1,
                             strict=True, sort_key_method=None, query=None,
                             restricted=False, **kw):
      # XXX: about "strict" parameter: This is a transition parameter,
      # allowing someone hitting a bug to revert to original behaviour easily.
      # It is not a correct name, as pointed out by Jerome. But instead of
      # searching for another name, it would be much better to just remove it.
      """
      Search all predicates which corresponds to this particular
      context.

      - sort_method parameter should not be used, if possible, because
        it can be very slow. Use sort_key_method instead.

      - sort_key_method parameter is passed to list.sort as key parameter if it
        is not None. This allows to sort the list of predicates found. The most
        important predicate is the first one in the list.

      - ignored_category_list:  this is the list of category that we do
        not want to test. For example, we might want to not test the
        destination or the source of a predicate.

      - tested_base_category_list:  this is the list of category that we do
        want to test. For example, we might want to test only the
        destination or the source of a predicate.

      - the acquired parameter allows to define if we want to use
        acquisition for categories. By default we want.

      - strict: if True, generate SQL which will match predicates matching
        all those categories at the same time, except for categories they do
        not check at all. Example:
          Predicate_1 checks foo/bar
          Predicate_2 checks foo/baz region/somewhere
          Predicate_3 checks foo/bar region/somewhere
          When called with category list ['foo/bar', 'region/somewhere'] and
          strict parameter to True, it will return [Predicate_1, Predicate_3].
          With strict to False or by not giving a category list, it would also
          return Predicate_2, because it matches on one criterion out of the 2
          it checks.
        Note that it changes the value returned by this function if it was
        invoked with "test=False" value. Otherwise, it should only change
        execution duration.
      """
      portal = self.getPortalObject()
      portal_catalog = portal.portal_catalog
      portal_categories = portal.portal_categories
      # Search the columns of the predicate table
      range_column_set = set()
      query_list = [] if query is None else [query]
      for column in portal_catalog.getColumnIds():
        if column[:10] == 'predicate.' and \
           column[-10:] in ('_range_min', '_range_max'):
          property_name = column[10:-10]
          if property_name not in range_column_set:
            range_column_set.add(property_name)
            # We have to check a range property
            equality = 'predicate.' + property_name
            range_min = equality + '_range_min'
            range_max = equality + '_range_max'

            value = context.getProperty(property_name)

            query = ComplexQuery(
                Query(**{equality: None}),
                Query(**{range_min: None}),
                Query(**{range_max: None}),
                logical_operator='AND')

            if value is not None:
              query = ComplexQuery(
                  query,
                  ComplexQuery(
                    Query(**{equality: value}),
                    ComplexQuery(
                      ComplexQuery(
                        Query(**{range_min: dict(query=value, range='ngt',)}),
                        Query(**{range_max: None}),
                        logical_operator='AND',),
                      ComplexQuery(
                        Query(**{range_min: None}),
                        Query(**{range_max: dict(query=value, range='min',)}),
                        logical_operator='AND',),
                      ComplexQuery(
                        Query(**{range_min: dict(query=value, range='ngt',)}),
                        Query(**{range_max: dict(query=value, range='min',)}),
                        logical_operator='AND',),
                      logical_operator='OR',),
                    logical_operator='OR',
                    ),
                  logical_operator='OR')

            query_list.append(query)

      # Add category selection
      if tested_base_category_list is None:
        if acquired:
          category_list = context.getAcquiredCategoryList()
        else:
          category_list = context.getCategoryList()
      else:
        if acquired:
          getter = context.getAcquiredCategoryMembershipList
        else:
          getter = context.getCategoryMembershipList
        category_list = []
        extend = category_list.extend
        for tested_base_category in tested_base_category_list:
          extend(getter(tested_base_category, base=1))

      if tested_base_category_list != []:
        preferred_predicate_category_list = portal.portal_preferences.getPreferredPredicateCategoryList()

        if (preferred_predicate_category_list and
            tested_base_category_list is not None and
            set(preferred_predicate_category_list).issuperset(tested_base_category_list)):
          # New behavior is enabled only if preferred predicate category is
          # defined and tested_base_category_list is passed.
          predicate_category_query_list = []
          predicate_category_table_name_list = []
          category_dict = {}
          for relative_url in category_list:
            category_value = portal_categories.getCategoryValue(relative_url)
            base_category_id = portal_categories.getBaseCategoryId(relative_url)
            base_category_value = portal_categories.getCategoryValue(base_category_id)
            if not base_category_value in category_dict:
              category_dict[base_category_value] = []
            category_dict[base_category_value].append(category_value)

          for base_category_value, category_value_list in category_dict.iteritems():
            if base_category_value.getId() in preferred_predicate_category_list:
              table_index = len(predicate_category_query_list)
              predicate_category_table_name = 'predicate_category_for_domain_tool_%s' % table_index
              table_alias_list = [('predicate_category', predicate_category_table_name)]
              predicate_category_query_list.append(
                  ComplexQuery(
                      Query(predicate_category_base_category_uid=base_category_value.getUid(), table_alias_list=table_alias_list),
                      Query(predicate_category_category_strict_membership=1, table_alias_list=table_alias_list),
                      ComplexQuery(
                          Query(predicate_category_category_uid=[category_value.getUid() for category_value in category_value_list], table_alias_list=table_alias_list),
                          Query(predicate_category_category_uid='NULL', table_alias_list=table_alias_list),
                          logical_operator='OR'),
                      logical_operator='AND'))

          if not predicate_category_query_list:
            # Prevent matching everything
            predicate_category_query_list.append(Query(predicate_category_base_category_uid=0))

          predicate_category_query = ComplexQuery(
              logical_operator='AND',
              *predicate_category_query_list)
          query_list.append(predicate_category_query)
        else:
          # Traditional behavior
          category_expression_dict = portal_categories.buildAdvancedSQLSelector(
                                             category_list or ['NULL'],
                                             query_table='predicate_category',
                                             none_sql_value=0,
                                             strict=strict)
          where_expression = category_expression_dict['where_expression']
          if where_expression:
            kw['where_expression'] = SQLQuery(where_expression)

          if 'from_expression' in category_expression_dict:
            kw['from_expression'] = category_expression_dict['from_expression']
          else:
            # Add predicate_category.uid for automatic join
            kw['predicate_category.uid'] = '!=NULL'

      if query_list:
        kw['query'] = ComplexQuery(logical_operator='AND', *query_list)

      if restricted:
        sql_result_list = portal_catalog.searchResults(**kw)
      else:
        sql_result_list = portal_catalog.unrestrictedSearchResults(**kw)
      if kw.get('src__'):
        return sql_result_list
      result_list = []
      if sql_result_list:
        if test:
          cache = {}
          def isMemberOf(context, c, strict_membership):
            if c in cache:
              return cache[c]
            cache[c] = result = portal_categories.isMemberOf(
              context, c, strict_membership=strict_membership)
            return result
        for predicate in sql_result_list:
          predicate = predicate.getObject()
          if not test or predicate.test(context, tested_base_category_list,
                                        isMemberOf=isMemberOf):
            result_list.append(predicate)
        if filter_method is not None:
          result_list = filter_method(result_list)
        if sort_key_method is not None:
          result_list.sort(key=sort_key_method)
        elif sort_method is not None:
          result_list.sort(cmp=sort_method)
      return result_list

    # XXX FIXME method should not be public
    # (some users are not able to see resource's price)
    security.declarePublic('generateMappedValue')
    def generateMappedValue(self, context, test=1, predicate_list=None, **kw):
      """
      We will generate a mapped value with the list of all predicates
      found.
      Let's say we have 3 predicates (in the order we want) like this:
      Predicate 1   [ base_price1,           ,   ,   ,    ,    , ]
      Predicate 2   [ base_price2, quantity2 ,   ,   ,    ,    , ]
      Predicate 3   [ base_price3, quantity3 ,   ,   ,    ,    , ]
      Our generated MappedValue will have the base_price of the
      predicate1, and the quantity of the Predicate2, because Predicate
      1 is the first one which defines a base_price and the Predicate2
      is the first one wich defines a quantity.
      """
      # First get the list of predicates
      if predicate_list is None:
        predicate_list = self.searchPredicateList(context, test=test, **kw)
      if len(predicate_list)==0:
        # No predicate, return None
        mapped_value = None
      else:
        # Generate tempDeliveryCell
        from Products.ERP5Type.Document import newTempSupplyCell
        mapped_value = newTempSupplyCell(self.getPortalObject(),
                                           'new_mapped_value')
        mapped_value_property_dict = {}
        # Look for each property the first predicate which defines the
        # property
        for predicate in predicate_list:
          getMappedValuePropertyList = getattr(predicate,
            'getMappedValuePropertyList', None)
          # searchPredicateList returns a list of any kind of predicate, which
          # includes predicates not containing any mapped value (for exemple,
          # domains). In such case, it has no meaning to handle them here.
          # A better way would be to tell catalog not to provide us with those
          # extra object, but there is no simple way (many portal types inherit
          # from MappedValue defining the accessor).
          # Feel free to improve.
          if getMappedValuePropertyList is not None:
            for mapped_value_property in predicate.getMappedValuePropertyList():
              if not mapped_value_property_dict.has_key(mapped_value_property):
                value = predicate.getProperty(mapped_value_property)
                if value is not None:
                  mapped_value_property_dict[mapped_value_property] = value
        # Update mapped value
        mapped_value.edit(**mapped_value_property_dict)
      return mapped_value

    # XXX FIXME method should not be public
    # (some users are not able to see resource's price)
    security.declarePublic('generateMultivaluedMappedValue')
    def generateMultivaluedMappedValue(self, context, test=1,
        predicate_list=None, explanation_only=0, **kw):
      """
      We will generate a mapped value with the list of all predicates
      found.
      Let's say we have 3 predicates (in the order we want) like this:
      Predicate 1   [ base_price1,           ,   ,   ,    ,    , ]
      Predicate 2   [ base_price2, additional_price2 ,   ,   ,    ,    , ]
      Predicate 3   [ base_price3, additional_price3 ,   ,   ,    ,    , ]
      Our generated MappedValue will take all values for each property and put
      them in lists, unless predicates define the same list of criterion categories
      """
      # First get the list of predicates
      if predicate_list is None:
        predicate_list = self.searchPredicateList(context, test=test, **kw)
      if predicate_list:
        from Products.ERP5Type.Document import newTempSupplyCell
        mapped_value_property_dict = defaultdict(list)
        explanation_dict = defaultdict(dict)
        # Look for each property the first predicate with unique criterion
        # categories which defines the property
        for predicate in predicate_list:
          full_prop_dict = explanation_dict[
            tuple(predicate.getMembershipCriterionCategoryList())]
          for mapped_value_property in predicate.getMappedValuePropertyList():
            if mapped_value_property in full_prop_dict:
              # we already have one value for this (categories, property)
              continue
            value = predicate.getProperty(mapped_value_property)
            if value is not None:
              full_prop_dict[mapped_value_property] = value
              mapped_value_property_dict[mapped_value_property].append(value)
        if explanation_only:
          return dict(explanation_dict)
        mapped_value = newTempSupplyCell(self.getPortalObject(),
                                         'multivalued_mapped_value')
        mapped_value._setMappedValuePropertyList(
          mapped_value_property_dict.keys())
        mapped_value.__dict__.update(mapped_value_property_dict)
        return mapped_value


    def getChildDomainValueList(self, parent, **kw):
      """
      Return child domain objects already present adn thois generetaded dynamically
      """
      # get static domain
      object_list = list(parent.objectValues())
      # get dynamic object generated from script
      object_list.extend(parent.getDomainGeneratorList(**kw))
      return object_list


    def getDomainByPath(self, path, default=_MARKER):
      """
      Return the domain object for a given path
      """
      path = path.split('/')
      base_domain_id = path[0]
      if default is _MARKER:
        domain = self[base_domain_id]
      else:
        domain = self.get(base_domain_id, _MARKER)
        if domain is _MARKER: return default
      for depth, subdomain in enumerate(path[1:]):
        domain_list = self.getChildDomainValueList(domain, depth=depth)
        for d in domain_list:
          if d.getId() == subdomain:
            domain = d
            break
        else:
          if domain is _MARKER: return default
          raise KeyError, subdomain
      return domain

InitializeClass(DomainTool)
