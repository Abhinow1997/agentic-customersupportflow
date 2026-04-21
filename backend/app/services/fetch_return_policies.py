class WalmartPolicyFetcher:
    """
    A service to return curated Walmart return and refund policies.

    Live scraping is intentionally disabled in this flow because the backend
    runs inside an async FastAPI request context on Windows, where the
    Playwright/Scrapling sync browser path is unreliable. The return flow only
    needs stable policy text, so we serve that directly from local policy data.
    """

    _LOCAL_POLICY_TEXT = {
        "standard_return_policy": {
            "source_url": "https://www.walmart.com/help/article/walmart-standard-return-policy/adc0dfb692954e67a4de206fb8d9e03a",
            "policy_title": "Standard Return Policy (90-day)",
            "content": """Walmart Standard Return Policy

You have 90 days after purchase or upon receipt to return most items unless noted in our exceptions. Most Consumer Electronics are returnable within 30 days. Wireless phones are returnable within 14 days.

To ensure your in-store item may be returned, review the exceptions on our Corporate Return Policy page. Most items purchased in-store or online from October 1 through December 31 are returnable until January 31. Marketplace seller participation varies.

If an item you received from Walmart.com is damaged or defective, your item may be eligible to be returned by mail or returned to any Walmart store and may qualify for a refund or replacement. Please start your return in the Walmart app or online by going to your Purchase History.

Express Bill Payments and fees associated with Walmart Financial Services products are non-refundable. Returns are available for nearly everything Walmart sells. Your purchase history on Walmart.com displays the latest eligible date for a return or replacement. However, we recommend keeping track of all manufacturer packaging and your receipt for a minimum of 90 days after purchase.

Walmart's policy applies to returns of products purchased in Walmart U.S. stores, Walmart.com, Walmart Business, or from Marketplace sellers on Walmart.com. Items purchased from dealers or resellers and not Walmart or Walmart.com directly are not eligible for return, refund, or exchange. Items sold and shipped by a Marketplace seller may be returned within 30 days.""",
        },
        "refund_processing": {
            "source_url": "https://www.walmart.com/help/article/refunds/a86a0400e237444cb9a5f3c3ce500d1b",
            "policy_title": "Refund Processing & Timelines",
            "content": """Walmart Refund Processing

We refund Walmart.com returns submitted in-store or by mail to your original method of payment. Outbound shipping charges are not always refunded upon return. This can include regular and freight shipping, and any shipping surcharges.

Debit and credit card refunds will be available in up to 10 business days. If your purchase was made using a debit or credit card, we will issue the refund to that same card. If the original card is not present and is not available by scanning the receipt, your refund is processed onto a Walmart shopping card or gift card.

For purchases linked to an international bank, refunds may take up to 30 business days.

If you do not have your receipt, show us your valid government-issued photo identification. We will accept your return if your identification information matches with the one stored in our secured database. Without a receipt you can: Exchange the item with another item. Get a Walmart gift card. If available, send the item to the manufacturer for repair.

If you cancel your order before your item ships, we release the authorization hold on your payment method. If the item has already shipped, we are not able to cancel the order. You can return the item for a refund.""",
        },
        "free_returns": {
            "source_url": "https://www.walmart.com/cp/returns/1231920",
            "policy_title": "Free Returns & Non-Returnable Items",
            "content": """Free Returns at Walmart

Walmart returns are free and easy. Items can be returned by mail or at your store.

Non-Returnable Items include: Prescription medications and devices. Items containing pseudoephedrine, ephedrine, phenylpropanolamine. Diabetic supplies including meters, testers, strips, lancets, lancet devices, syringes. Sex toys and vibrators. Pregnancy, ovulation, COVID-19 tests and home diagnostic testing kits. Home hygiene medical equipment such as bedpans, bath seats, opened or unsealed breast pumps. Firearms and ammunition. Airsoft and air guns, BB guns, Crossbows, Vertical or archery bows. Pepper spray. Bear spray.

Also non-returnable: Walmart Express bill payments. Reloadable debit or credit cards. Check or card cashing fees. Branded gift cards including Visa, MC, AmEx. Prepaid cell phone minutes. Lottery. Video on demand. Sim cards. Gift cards. Precious metals and coins. Alcohol including Beer, Wine, Spirits. Tobacco Products.

Some third-party marketplace sellers may charge a restocking fee up to 20 percent. Some examples include luxury goods and items that are considered freight such as major appliances, heavy furniture.

Before returning to the store: Bring the items you would like to return, including all original packaging and accessories. Mark out any original shipping labels to avoid shipping errors or refund delays. Review the return refund summary and submit your return. Bring any receipts for those items, if available.""",
        },
    }

    def __init__(self):
        self.fetch_config = {
            "headless": False,
            "network_idle": False,
            "timeout": 0,
        }

    def _fallback_policy(self, key: str):
        policy = self._LOCAL_POLICY_TEXT.get(key)
        if not policy:
            return None
        return {
            "source_url": policy["source_url"],
            "policy_title": policy["policy_title"],
            "content": policy["content"],
            "retrieval_mode": "local_fallback",
        }

    def _bundle_policies(self, *keys: str) -> dict | None:
        parts = []
        title_parts = []
        source_urls = []

        for key in keys:
            policy = self._LOCAL_POLICY_TEXT.get(key)
            if not policy:
                continue
            title_parts.append(policy["policy_title"])
            source_urls.append(policy["source_url"])
            parts.append(f"## {policy['policy_title']}\n{policy['content']}")

        if not parts:
            return None

        return {
            "source_url": " | ".join(source_urls),
            "policy_title": " + ".join(title_parts),
            "content": "\n\n".join(parts),
            "retrieval_mode": "local_bundle",
        }

    def _fetch_article_content(self, url: str):
        """Return curated local policy text for the requested policy URL."""
        # Standard return policy
        if "walmart-standard-return-policy" in url:
            policy = self._LOCAL_POLICY_TEXT["standard_return_policy"]
            return {
                "source_url": policy["source_url"],
                "policy_title": policy["policy_title"],
                "content": policy["content"],
                "retrieval_mode": "local_fallback",
            }

        # Refund timelines
        if "refunds" in url:
            policy = self._LOCAL_POLICY_TEXT["refund_processing"]
            return {
                "source_url": policy["source_url"],
                "policy_title": policy["policy_title"],
                "content": policy["content"],
                "retrieval_mode": "local_fallback",
            }

        # Marketplace policy and restrictions
        if "marketplace-return-policy-return-restrictions" in url:
            return self._bundle_policies("standard_return_policy", "free_returns")
        if "marketplace-return-policy" in url:
            return self._bundle_policies("standard_return_policy", "free_returns")

        # Major appliance guide
        if "major-appliances" in url:
            return self._bundle_policies("standard_return_policy", "free_returns")

        return self._fallback_policy("standard_return_policy")

    def get_standard_return_policy(self):
        """Fetches the 90-day foundational return policy."""
        url = "https://www.walmart.com/help/article/walmart-standard-return-policy/adc0dfb692954e67a4de206fb8d9e03a"
        return self._fetch_article_content(url)

    def get_refund_timelines(self):
        """Fetches rules regarding how and when refunds are issued."""
        url = "https://www.walmart.com/help/article/refunds/a86a0400e237444cb9a5f3c3ce500d1b"
        return self._fetch_article_content(url)

    def get_marketplace_policy(self):
        """Fetches policies for third-party sellers (Walmart Marketplace)."""
        url = "https://www.walmart.com/help/article/walmart-marketplace-return-policy/63c3566a9d3546858582acae2fbfdb7e"
        return self._fetch_article_content(url)

    def get_marketplace_restrictions(self):
        """Fetches specific item restrictions for Marketplace returns."""
        url = "https://www.walmart.com/help/article/walmart-marketplace-return-policy-return-restrictions/5fb8d5f42f0d4e09bdb5b89fd1f33e1b"
        return self._fetch_article_content(url)

    def get_major_appliance_policy(self):
        """Fetches the specific guide for high-value major appliance returns."""
        url = "https://www.walmart.com/help/article/marketplace-major-appliances-purchase-and-returns-guide/85502dae20644114b76cfa534ff9e20d"
        return self._fetch_article_content(url)
