from Products.ERP5.Document.Image import Image
from zLOG import LOG,INFO,ERROR,WARNING

class TileImage(Image):
  """
  Tile Images split images in many small parts and then store informations as sub objects
  """

  def _setFile(self, *args, **kw):
    """Set the file content and reset image information."""
    if "TileGroup0" in self.objectIds():
        self.manage_delObjects("TileGroup0")
    if "ImageProperties.xml" in self.objectIds():
        self.manage_delObjects("ImageProperties.xml")
    self._update_image_info()
    processor = self.Image_getERP5ZoomifyProcessor(self)
    processor.ZoomifyProcess(self.getId(),*args)

