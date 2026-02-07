from orket.settings import load_user_settings
from orket.vendors.base import VendorInterface
from orket.vendors.local import LocalVendor
from orket.vendors.gitea import GiteaVendor

def get_vendor() -> VendorInterface:
    settings = load_user_settings()
    vendor_type = settings.get("vendor_type", "local").lower()
    
    if vendor_type == "gitea":
        config = settings.get("gitea_config", {})
        return GiteaVendor(
            base_url=config.get("url"),
            token=config.get("token"),
            owner=config.get("owner"),
            repo=config.get("repo")
        )
    elif vendor_type == "ado":
        # from orket.vendors.ado import ADOVendor
        # return ADOVendor(...)
        pass
    elif vendor_type == "jira":
        # from orket.vendors.jira import JiraVendor
        # return JiraVendor(...)
        pass
        
    return LocalVendor(department=settings.get("active_department", "core"))
