# app/rag/seed.py
"""
Quick-seed ChromaDB with key Walmart policy data.

Run this to test the full LangGraph pipeline immediately --
no scrapling or web scraping required. Uses the policy details
we already collected.

Usage:
    cd backend
    python -m app.rag.seed          # seed all domains
    python -m app.rag.seed --stats  # check what's in ChromaDB
"""
from __future__ import annotations

import logging
import argparse

from app.rag.chunker import chunk_policy_text
from app.rag.store import get_store

logger = logging.getLogger("rag.seed")

# ── Pre-collected policy content ──────────────────────────────────────────
# This is the actual policy data from Walmart's public pages, summarized
# into clean text blocks. Enough for the RAG pipeline to return grounded
# citations while you get scrapling set up for the full scrape.

SEED_POLICIES = [
    {
        "domain": "returns",
        "policy_name": "Standard Return Policy (90-day)",
        "priority": "CRITICAL",
        "source_url": "https://www.walmart.com/help/article/walmart-standard-return-policy/adc0dfb692954e67a4de206fb8d9e03a",
        "content": """Walmart Standard Return Policy

You have 90 days after purchase or upon receipt to return most items unless noted in our exceptions. Most Consumer Electronics are returnable within 30 days. Wireless phones are returnable within 14 days.

To ensure your in-store item may be returned, review the exceptions on our Corporate Return Policy page. Most items purchased in-store or online from October 1 through December 31 are returnable until January 31. Marketplace seller participation varies.

If an item you received from Walmart.com is damaged or defective, your item may be eligible to be returned by mail or returned to any Walmart store and may qualify for a refund or replacement. Please start your return in the Walmart app or online by going to your Purchase History.

Express Bill Payments and fees associated with Walmart Financial Services products are non-refundable. Returns are available for nearly everything Walmart sells. Your purchase history on Walmart.com displays the latest eligible date for a return or replacement. However, we recommend keeping track of all manufacturer packaging and your receipt for a minimum of 90 days after purchase.

Walmart's policy applies to returns of products purchased in Walmart U.S. stores, Walmart.com, Walmart Business, or from Marketplace sellers on Walmart.com. Items purchased from dealers or resellers and not Walmart or Walmart.com directly are not eligible for return, refund, or exchange. Items sold and shipped by a Marketplace seller may be returned within 30 days.""",
    },
    {
        "domain": "returns",
        "policy_name": "Free Returns & Non-Returnable Items",
        "priority": "CRITICAL",
        "source_url": "https://www.walmart.com/cp/returns/1231920",
        "content": """Free Returns at Walmart

Walmart returns are free and easy. Items can be returned by mail or at your store.

Non-Returnable Items include: Prescription medications and devices. Items containing pseudoephedrine, ephedrine, phenylpropanolamine. Diabetic supplies including meters, testers, strips, lancets, lancet devices, syringes. Sex toys and vibrators. Pregnancy, ovulation, COVID-19 tests and home diagnostic testing kits. Home hygiene medical equipment such as bedpans, bath seats, opened or unsealed breast pumps. Firearms and ammunition. Airsoft and air guns, BB guns, Crossbows, Vertical or archery bows. Pepper spray. Bear spray.

Also non-returnable: Walmart Express bill payments. Reloadable debit or credit cards. Check or card cashing fees. Branded gift cards including Visa, MC, AmEx. Prepaid cell phone minutes. Lottery. Video on demand. Sim cards. Gift cards. Precious metals and coins. Alcohol including Beer, Wine, Spirits. Tobacco Products.

Some third-party marketplace sellers may charge a restocking fee up to 20 percent. Some examples include luxury goods and items that are considered freight such as major appliances, heavy furniture.

Before returning to the store: Bring the items you would like to return, including all original packaging and accessories. Mark out any original shipping labels to avoid shipping errors or refund delays. Review the return refund summary and submit your return. Bring any receipts for those items, if available.""",
    },
    {
        "domain": "returns",
        "policy_name": "Refund Processing & Timelines",
        "priority": "HIGH",
        "source_url": "https://www.walmart.com/help/article/refunds/a86a0400e237444cb9a5f3c3ce500d1b",
        "content": """Walmart Refund Processing

We refund Walmart.com returns submitted in-store or by mail to your original method of payment. Outbound shipping charges are not always refunded upon return. This can include regular and freight shipping, and any shipping surcharges.

Debit and credit card refunds will be available in up to 10 business days. If your purchase was made using a debit or credit card, we will issue the refund to that same card. If the original card is not present and is not available by scanning the receipt, your refund is processed onto a Walmart shopping card or gift card.

For purchases linked to an international bank, refunds may take up to 30 business days.

If you do not have your receipt, show us your valid government-issued photo identification. We will accept your return if your identification information matches with the one stored in our secured database. Without a receipt you can: Exchange the item with another item. Get a Walmart gift card. If available, send the item to the manufacturer for repair.

If you cancel your order before your item ships, we release the authorization hold on your payment method. If the item has already shipped, we are not able to cancel the order. You can return the item for a refund.""",
    },
    {
        "domain": "pricing",
        "policy_name": "Price Match Policy",
        "priority": "HIGH",
        "source_url": "https://www.walmart.com/help/article/walmart-price-match-policy/6295d9e1a501489b9aa40a60c899b288",
        "content": """Walmart Price Match Policy

Our Price Match policies differ between Walmart stores and Walmart.com. For items purchased in a Walmart U.S. store, we will match the price of the identical item advertised on Walmart.com. Restrictions apply. The Walmart Store Manager on duty has the final decision on any Price Match.

We strive to offer the best possible price on Walmart.com every day, on all items. As a result, we do not offer any price matching for items offered on our website.

We do NOT price match the following: Prices offered by competitors. Prices for items previously purchased on Walmart.com that have since decreased in price. Prices available through Marketplace or offered by third-party sellers. Items offered in our Walmart stores or Neighborhood Markets.

Additional restrictions: Walmart.com prices from special events including but not limited to clearance, Rollback, Black Friday or Cyber Monday deals, or other limited-time promotions. Prices from Marketplace retailers or third-party sellers. One price match per customer per day. Not available in Alaska, Hawaii, or Puerto Rico. Item must be in stock on Walmart.com and identical in brand, model, size, and specification.

There is no post-purchase price adjustment policy. If the price drops after purchase, the only option is to return and rebuy within the return window.""",
    },
    {
        "domain": "coupons",
        "policy_name": "Coupon Policy (OP-41)",
        "priority": "HIGH",
        "source_url": "https://corporate.walmart.com/policies",
        "content": """Walmart Coupon Policy (OP-41) Updated October 2025

Walmart accepts valid paper manufacturer coupons with a scannable GS1 barcode that validates to Walmart's master file. We only accept coupons for merchandise that we sell.

Key rules: Coupons must be presented at the time of purchase. Only one paper manufacturer coupon per item for in-store purchases only. Limit of 4 identical coupons per household per day unless otherwise noted on coupon. There is no limit on the number of coupons (variety) that can be used in a total transaction.

Walmart does not give cash back nor will any overages apply to the remaining items in the transaction if the value of a coupon is greater than the purchase value of the item, including WIC and SNAP. The value of a coupon will be applied up to the price of the item and any excess value will not be applied to the transaction total.

Acceptance of unmatched coupons is against policy and will be systematically denied.

Walmart does NOT accept: Digital or mobile coupons. Expired coupons. Competitor or retailer coupons. Counterfeit coupons. Vouchers or gift certificates. UPC-A coupon barcodes. Double or triple coupons. BOGO manufacturer coupons with a percentage.

Returns of items purchased with coupons: The refund credit will not include any manufacturer coupon credit that applied to the original transaction. Manufacturer coupons are prohibited on prepaid products, gift cards, and digital devices.

BOGO (Buy One Get One Free) manufacturer coupons are accepted. Two BOGO manufacturer coupons cannot be combined to get both items free. Store Management has the final decision in taking care of the customer.""",
    },
    {
        "domain": "walmart_plus",
        "policy_name": "Walmart+ Membership Benefits & Terms",
        "priority": "CRITICAL",
        "source_url": "https://www.walmart.com/plus",
        "content": """Walmart+ Membership

Pricing: Standard membership costs 12.95 dollars per month or 98 dollars per year. Walmart+ Assist (for government aid recipients and students) costs 6.47 dollars per month or 49 dollars per year. Free 30-day trial available.

Core Benefits: Free delivery from stores on orders of 35 dollars or more, with same-day available. Members save up to 9.95 on total fees for Express Delivery. If under 35 dollars, members can pay an extra 2.95 for same day shipping. Members do not pay the 7.95 to 9.95 delivery fee. There is a 35 dollar order minimum for free delivery. Under 35 dollars there is a minimum order fee of 6.99.

Free next-day and two-day shipping from Walmart.com with no order minimum. Excludes most Marketplace items. Freight and location surcharges may apply.

Additional Benefits: Video streaming with choice between Paramount+ Essential or Peacock Premium, switchable every 90 days. Fuel savings up to 10 cents per gallon at over 13000 Exxon, Mobil, Walmart, and Murphy stations. Returns from home with no repacking or printing needed at select locations. Free pharmacy delivery for eligible medications, same-day with no minimum. Walmart+ Travel powered by Expedia: up to 5 percent Walmart Cash on hotels, 2 percent on flights. Early access to sales and special product releases. Free flat tire repair at Walmart Auto Care Centers. Burger King: 25 percent off once per day, free Whopper once per quarter. Scan and Go mobile checkout in stores.

Cancellation: Members can cancel anytime. Benefits continue until end of current billing period. Trial cancellation terminates benefits immediately. No prorated refunds. The Walmart+ Membership fee is non-refundable except as expressly set forth in the Terms. Auto-renewal charges payment on file unless canceled before term end.""",
    },
    {
        "domain": "shipping",
        "policy_name": "Shipping & Delivery Benefits",
        "priority": "HIGH",
        "source_url": "https://www.walmart.com/help/article/walmart-benefits-free-shipping-and-free-delivery-from-your-store/d1738a201207485c99fd53ccdbc49699",
        "content": """Walmart Shipping and Delivery

Non-members: Free shipping on orders of 35 dollars or more for eligible items. Standard shipping takes 2 to 5 business days. Free 2-day shipping on eligible items with 35 dollar minimum.

Walmart+ members: Free shipping with no order minimum on items sold by Walmart or shipped by Walmart. Next-day and two-day arrival on thousands of items. Excludes most Marketplace items. Freight and location surcharges may apply.

Same-day delivery: Available for Walmart+ members with 35 dollar order minimum from local store. Express delivery available for additional 10 dollar fee. Walmart+ members save up to 9.95 on total fees for Express Delivery.

Marketplace items: Shipping varies by seller. Value shipping offers free delivery in continental 48 states with transit time of 3 to 7 business days. TwoDay shipping available to eligible sellers. Freight shipping transit time is 5 to 10 business days.

Walmart calculates Expected Delivery Dates based on seller fulfillment lag time, operational days, and carrier transit data. Orders 5 or more days past the EDD with no carrier movement may be auto-canceled with a refund.""",
    },
    {
        "domain": "warranty",
        "policy_name": "Protection Plans by Allstate",
        "priority": "HIGH",
        "source_url": "https://www.walmart.com/help/article/walmart-protection-plans-by-allstate/87e60d4d34b340e0adfe815afe402d19",
        "content": """Walmart Protection Plans by Allstate

Walmart partners with Allstate (formerly SquareTrade) for extended protection plans. Plans can be purchased at checkout or within 30 days of product purchase.

Standard Plan: Covers mechanical and electrical failures, power surges, power failures, and breakdowns from normal use. For TVs, monitors, appliances, power tools, lawn and garden products. The Standard Plan extends the manufacturer's warranty.

Accident Plan: Covers drops, cracked screens, and liquid damage in addition to everything covered by the Standard Plan. For laptops, tablets, smartphones, and headphones.

Claims Process: File online at WalmartProtection.com or call 1-877-538-4389. Receipt required to file a claim. Many claims are approved instantly; otherwise a specialist will guide you through next steps. Resolution: repair first, then replacement or reimbursement if repair is not possible.

To register your receipt, text an image of it to 202202. Registration is not necessary for your plan to be active.

Exclusions: Intentional damage, theft, and loss are not covered. Pet or child damage is excluded under standard plans. Manufacturer warranty must expire before protection plan coverage begins for standard plans.

Cancellation: During the first 30 days, for in-store purchases bring the receipt back for a full refund. For online purchases, cancel through Walmart.com account. After 30 days, contact Allstate for a prorated refund.""",
    },
    {
        "domain": "pharmacy",
        "policy_name": "$4 Generic Prescription Program",
        "priority": "MEDIUM",
        "source_url": "https://www.walmart.com/cp/4-prescriptions/1078664",
        "content": """Walmart $4 Prescription Program

The Walmart Prescription Program provides generic medications at 4 dollars for a 30-day supply or 10 dollars for a 90-day supply. The program requires no membership, no fees, and no insurance.

Over 300 generic medications are available covering diabetes, blood pressure, cholesterol, thyroid, mental health, and other conditions. Your healthcare provider must provide an active prescription before filling.

Key restrictions: Generic drugs only, brand-name medications not covered. Specific dosages only, higher doses cost more. Pricing may vary by state, specifically CA and MN. Not available in North Dakota. First fills must be picked up in-store; refills eligible for mail order. Mail order is 90-day supplies only, with 10 dollar delivery fee which is waived for Walmart+ members. Program subject to change without notice.

Prescription transfers: Visit the Walmart Pharmacy page and click Transfer Prescriptions to move your prescription from another retailer to Walmart.""",
    },
    {
        "domain": "product_safety",
        "policy_name": "Product Quality & Safety",
        "priority": "MEDIUM",
        "source_url": "https://corporate.walmart.com/suppliers/requirements/compliance-areas",
        "content": """Walmart Product Safety and Compliance

Walmart earns customer trust by providing safe, high-quality products. Suppliers must meet all legal, industry, and Walmart safety, quality, and technical requirements.

Product Recalls: Recalled items receive full refund regardless of purchase condition. WIC and SNAP restrictions apply. Suppliers must notify Walmart of voluntary and mandatory product recalls and participate actively with Walmart and regulatory authorities in recall processes.

Food Safety: Walmart follows FDA FSMA regulations. Food products must comply with FDA regulations, FTC and USDA guidelines, and Federal Meat Inspection Act and Poultry Products Inspection Act. Food must be labeled for U.S. retail sale and packaged to prevent contamination.

Chemicals and Hazardous Materials: Products containing chemicals, aerosols, or batteries require Safety Data Sheets. WERCS registration required for chemical assessment.

Defective Products: Eligible for return or exchange under standard return policy. Safety-related defects trigger compliance escalation to the product safety team.""",
    },
    {
        "domain": "privacy",
        "policy_name": "Customer Privacy Notice",
        "priority": "MEDIUM",
        "source_url": "https://corporate.walmart.com/privacy-security/walmart-privacy-notice",
        "content": """Walmart Customer Privacy Notice

Walmart collects personal information through online and mobile interactions, in-store purchases, cameras, Wi-Fi, Bluetooth beacons, and voice assistants. Data collected includes financial information, geolocation, sensory information, and purchase history.

Customer rights include: Access to personal information collected. Ability to update information. Opt-out of data selling or sharing for cross-context behavioral advertising. Delete personal information on request.

California residents have additional CCPA rights including access, deletion, and opt-out. Submit requests through Your Privacy Rights link or call 1-800-Walmart and say Privacy.

Walmart uses reasonable information security measures including physical, administrative, and technical safeguards. Data retained as long as necessary for purposes described or as permitted by law.

For medical information through pharmacy and vision services, separate Notice of Privacy Practices applies.""",
    },
    {
        "domain": "legal",
        "policy_name": "Gift Card Terms & Conditions",
        "priority": "MEDIUM",
        "source_url": "https://business.walmart.com/help/article/gift-card-terms-and-conditions/e949c6cb64354a779868406c7b5033d8",
        "content": """Walmart Gift Card Terms and Conditions

Walmart Gift Cards are non-refundable and have no expiration date. They include a mandatory arbitration provision requiring arbitration on an individual basis to resolve disputes.

Gift cards cannot be purchased with manufacturer coupons and are not eligible for returns. Branded third-party gift cards (iTunes, Visa, MC, AmEx etc.) have separate issuer terms and conditions.

Customers in Puerto Rico authorize Walmart to share personal information with applicable government agencies as required by law for possible financial exploitation cases.""",
    },
    {
        "domain": "accessibility",
        "policy_name": "Accessibility Policy",
        "priority": "MEDIUM",
        "source_url": "https://www.walmart.com/help/article/responsible-disclosure-and-accessibility-policies/0f173dab8bd942da84b1cd7ab5ffc3cb",
        "content": """Walmart Accessibility Policy

Walmart is committed to making its website accessible for all customers, including those with disabilities. Efforts are guided by the Web Content Accessibility Guidelines version 2.1 Level AA (WCAG 2.1 AA).

For assistance accessing website content, customers can reach Customer Care at 1-800-966-6546. Service animals are permitted in all Walmart stores per ADA requirements. Walmart's Ethics Office handles ADA title III related complaints received at 1-800-963-8442.""",
    },
]


def seed_chromadb():
    """Seed ChromaDB with pre-collected Walmart policy data."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    store = get_store()
    total_chunks = 0

    for policy in SEED_POLICIES:
        chunks = chunk_policy_text(
            policy["content"],
            source_url=policy["source_url"],
            domain=policy["domain"],
            policy_name=policy["policy_name"],
            priority=policy["priority"],
        )
        store.upsert_chunks(chunks)
        total_chunks += len(chunks)
        logger.info(
            "  %s/%s -> %d chunks",
            policy["domain"], policy["policy_name"], len(chunks),
        )

    logger.info("Seeded %d total chunks across %d policies", total_chunks, len(SEED_POLICIES))
    return total_chunks


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    parser = argparse.ArgumentParser(description="Seed ChromaDB with Walmart policy data")
    parser.add_argument("--stats", action="store_true", help="Show ChromaDB stats")
    parser.add_argument("--query", "-q", type=str, help="Test query")
    args = parser.parse_args()

    if args.stats:
        store = get_store()
        stats = store.get_stats()
        print(f"\nChromaDB: {stats['total_chunks']} chunks")
        for domain, count in stats.get("domains", {}).items():
            print(f"  {domain:<20} {count} chunks")
        return

    if args.query:
        store = get_store()
        results = store.query_by_text(args.query, n_results=5)
        print(f"\nResults for '{args.query}':\n")
        for r in results:
            m = r["metadata"]
            print(f"  [{r['similarity']:.3f}] {m['domain']}/{m['policy_name']}")
            print(f"         Section: {m['section_header']}")
            print(f"         {r['content'][:150]}...\n")
        return

    seed_chromadb()


if __name__ == "__main__":
    main()
