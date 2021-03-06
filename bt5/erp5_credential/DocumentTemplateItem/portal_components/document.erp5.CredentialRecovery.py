##############################################################################
#
# Copyright (c) 2010 Nexedi SA and Contributors. All Rights Reserved.
#                    Fabien MORIN <fabien@nexedi.com>
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

from AccessControl import ClassSecurityInfo
from Products.ERP5Type import Permissions, PropertySheet
from Products.ERP5.Document.Ticket import Ticket
from Products.ERP5.mixin.encrypted_password import EncryptedPasswordMixin
try:
  from Products import PluggableAuthService
  from Products.ERP5Security.ERP5UserManager import ERP5UserManager
except ImportError:
  PluggableAuthService = None


class CredentialRecovery(Ticket, EncryptedPasswordMixin):
    """
    """

    meta_type = 'ERP5 Credential Recovery'
    portal_type = 'Credential Recovery'
    add_permission = Permissions.AddPortalContent

    # Declarative security
    security = ClassSecurityInfo()
    security.declareObjectProtected(Permissions.AccessContentsInformation)

    # Declarative properties
    property_sheets = ( PropertySheet.CredentialQuestion
                      , PropertySheet.DefaultCredentialQuestion
                      , PropertySheet.Login
                      , PropertySheet.Codification
                      , PropertySheet.Person
                      , PropertySheet.Url
                      )

    def isAnswerCorrect(self):
      '''
      Check if the given answer match the real answer
      The answer is not case sensitive
      '''
      related_person = self.getDestinationDecisionValue()
      if related_person is not None:
        real_answer = related_person.getDefaultCredentialQuestionAnswer()
        if real_answer is not None:
          proposed_answer = self.getDefaultCredentialQuestionAnswer()
          if proposed_answer is not None:
            return real_answer.lower() == proposed_answer.lower()
      return False
