# Track B: RAG Examples and Failure Cases

The first four examples are from the saved Track B harness run `rag_eval_20261015T225907.csv`. The fifth is a separate, unscored smoke test through `rag_invoke`. Inputs include each customer's profile and question, and outputs are reproduced from the corresponding run. The final section records two earlier failure cases and their fixes.

## Harness Input/Output Pairs

### 1. Gold member: online Outdoor and Footwear shopper

**Input — customer context**

```json
{
  "churn_probability": 0.81,
  "loyalty_tier": "Gold",
  "days_since_last_purchase": 47,
  "total_lifetime_value": 3120.40,
  "avg_order_value": 186.25,
  "category_diversity_score": 0.5,
  "online_to_store_ratio": 0.72,
  "top_categories": ["Outdoor", "Footwear"]
}
```

**Input — question**

> Generate a personalized retention offer for this at-risk Gold member who shops mostly online for outdoor gear and footwear.

**Output — generated offer**

**Subject:** Your Gold Benefits Are Waiting—Free Shipping & Returns on Your Next Order

**Body:**

We've noticed it's been a while since your last visit, and we'd love to have you back. As a Gold member, you're already enjoying free standard shipping on all orders and free return shipping—benefits that make shopping for outdoor gear and footwear easier than ever. Your 1.5× points earn rate also means every purchase gets you closer to rewards. Come back soon and take advantage of the perks you've earned.

**Rationale:**

The customer has a high churn probability (0.81) and hasn't purchased in 47 days. The retrieved context supports only the existing Gold tier benefits: free standard shipping (always), free return shipping, and 1.5× points earn rate. No new promotional offer, discount, bonus points, or spending threshold is documented in the policy context for this retention scenario. The message emphasizes existing membership value without inventing incentives, references the customer's primary shopping categories (outdoor and footwear) from the profile, and includes a clear call to action. The tone is warm and non-urgent, designed to re-engage without false scarcity or pressure.

### 2. Bronze member: in-store apparel shopper

**Input — customer context**

```json
{
  "churn_probability": 0.74,
  "loyalty_tier": "Bronze",
  "days_since_last_purchase": 68,
  "total_lifetime_value": 312.80,
  "avg_order_value": 41.15,
  "category_diversity_score": 0.125,
  "online_to_store_ratio": 0.20,
  "top_categories": ["Apparel"]
}
```

**Input — question**

> Generate a retention offer for this Bronze member who shops in store, buys only apparel, and has not purchased in over two months.

**Output — generated offer**

**Subject:** We miss you—come back and earn rewards on your next apparel purchase

**Body:**

It's been over two months since your last visit, and we'd love to see you back in store. As a Bronze member of NorthStar Summit Rewards, you earn 1× points on every purchase—and those points add up toward rewards. Stop by soon to shop apparel and start earning again. Your loyalty matters to us.

**Rationale:**

The customer has a 74% churn probability and has not purchased in 68 days. The retrieved policy context supports one active retention offer per member, valid for 45 days. However, the context does not authorize a specific discount, bonus points multiplier, dollar credit, or tier-upgrade incentive for this Bronze member. The policy explicitly prohibits inventing benefits or implying tier changes without documented support.

The retrieved context confirms Bronze members earn 1× points—an existing membership benefit, not a new offer. Mentioning this existing benefit reminds the customer of value without overstating the retention incentive. The message acknowledges the customer's in-store preference (online-to-store ratio 0.2) and apparel focus (top category), personalizes the greeting, and includes a clear call to action without false urgency or unsupported claims.

### 3. Platinum member: high-value customer with broad category interest

**Input — customer context**

```json
{
  "churn_probability": 0.66,
  "loyalty_tier": "Platinum",
  "days_since_last_purchase": 39,
  "total_lifetime_value": 8940.00,
  "avg_order_value": 447.00,
  "category_diversity_score": 0.75,
  "online_to_store_ratio": 0.55,
  "top_categories": ["Outdoor", "Electronics", "Home"]
}
```

**Input — question**

> Generate a retention offer for this high-value Platinum member with broad category interest and a large average order.

**Output — generated offer**

**Subject:** Your Platinum Perks Are Waiting—Let's Get You Back

**Body:**

We've noticed it's been a while since your last visit, and we'd love to welcome you back. As a Platinum member, you're already enjoying some great benefits—like your 60-day return window on eligible purchases, unlimited free gear repair, and 48-hour early access to our sales. Your $100 annual gear credit is also ready to use whenever you shop across Outdoor, Electronics, or Home categories. Stop by or shop online soon to make the most of your membership.

**Rationale:**

The customer is Platinum with high lifetime value ($8,940) and broad category engagement, but shows elevated churn risk (0.66) and hasn't purchased in 39 days. The retrieved policy context supports only existing Platinum tier benefits—no new promotional discount, bonus points, or spending threshold is documented. Mentioning concrete, verified benefits (60-day return window, unlimited repair, early access, $100 annual credit) reinforces membership value without inventing incentives. The message avoids false urgency, does not claim tier preservation tied to purchase, and includes a clear call to action aligned with the customer's demonstrated channel preference (online-to-store ratio 0.55) and top categories.

### 4. Silver member: just below the Gold lifetime-value threshold

**Input — customer context**

```json
{
  "churn_probability": 0.70,
  "loyalty_tier": "Silver",
  "total_lifetime_value": 1985.00,
  "days_since_last_purchase": 52,
  "avg_order_value": 132.30,
  "category_diversity_score": 0.375,
  "online_to_store_ratio": 0.61,
  "top_categories": ["Home", "Beauty"]
}
```

**Input — question**

> Generate a retention offer for this Silver member whose lifetime value is just under the Gold threshold.

**Output — generated offer**

**Subject:** Your Silver Rewards Are Closer to Gold Than You Think

**Body:**

We've noticed it's been a while since your last visit, and we'd love to welcome you back. As a Silver member, you're earning 1.25× points on every purchase and enjoying benefits like free standard shipping on orders over $50—plus early access to sales 12 hours before the general public. Your next purchase in Home or Beauty could be the perfect time to shop and earn toward your rewards. Come back soon and see what's new.

**Rationale:**

The customer's lifetime value ($1,985) is $15 short of the Gold threshold ($2,000), but the retrieved context explicitly states that tier is based on *trailing 12-month spend*, not lifetime value. The customer profile does not include trailing 12-month spend, so I cannot claim they are "close to Gold" without inventing unsupported data. The message instead reinforces existing Silver benefits (1.25× earn rate, free shipping threshold, early access) to encourage re-engagement without implying a tier upgrade is imminent or that a single purchase will change their status. No retention offer code, discount, bonus points, or deadline is invented; the 45-day retention offer window is not mentioned because no specific promotional incentive is supported by the retrieved context. The message focuses on reminding the customer of their current membership value and inviting them to shop in their preferred categories.

### 5. Silver member: online Beauty and Grocery shopper (smoke test)

**Input — customer context**

```json
{
  "churn_probability": 0.58,
  "loyalty_tier": "Silver",
  "total_lifetime_value": 1640.00,
  "days_since_last_purchase": 44,
  "avg_order_value": 82.00,
  "category_diversity_score": 0.25,
  "online_to_store_ratio": 0.86,
  "top_categories": ["Beauty", "Grocery"]
}
```

**Input — question**

> Generate a retention offer for this at-risk Silver member who shops mostly online for Beauty and Grocery.

**Output — generated offer**

**Subject:** Your Silver Benefits Are Waiting—Plus Early Access to Our Next Sale

**Body:**

We've noticed it's been a while since your last visit, and we'd love to have you back. As a Silver member, you're already earning 1.25× points on every purchase and enjoying free standard shipping on orders over $50—benefits that reward your loyalty with every transaction. Plus, you get 12-hour early access to our upcoming sales, so you can shop Beauty and Grocery picks before they sell out. Come back soon and keep earning rewards on the categories you love.

**Rationale:**

The customer is Silver tier with 44 days since last purchase and 0.58 churn probability. The retrieved context confirms Silver benefits: 1.25× points earn rate, free standard shipping at $50+, and 12-hour early access to sales. These are existing membership benefits, not new incentives. The message references the customer's top categories (Beauty and Grocery) from the profile and does not invent a discount, promo code, spending threshold, or expiration date. However, “before they sell out” implies product scarcity that the retrieved context does not establish; remove that phrase before treating this as a policy-grounded final offer. The message does not claim the customer will upgrade, downgrade, or lose tier status based on a purchase or return.



## Failure Cases and Fixes

The following two iterations use the same Gold customer context and question as Example 1. They are kept here as failures because they show specific ways an otherwise plausible retention message can overstate what policy supports. Their outputs are earlier iterations, not answers from the saved harness run; the chunk IDs below identify the saved retrieval context for this same Gold scenario (`CUST-10000317`), rather than claiming the earlier drafts were independently rerun.

**Retrieved chunk IDs for this Gold scenario:** `POL-LOY-011-s010-c001`, `KB-FAQ-022-s003-c001`, `KB-FAQ-022-s003-c002`, `POL-LOY-011-s013-c001`, `POL-LOY-011-s012-c001`, `POL-RET-004-s007-c001`.

### Failure 1: Existing benefits presented as a new promotion

**Retrieved chunk IDs:** `POL-LOY-011-s010-c001`, `KB-FAQ-022-s003-c001`, `KB-FAQ-022-s003-c002`, `POL-LOY-011-s013-c001`, `POL-LOY-011-s012-c001`, `POL-RET-004-s007-c001`.

**Input:** Same customer context and question as Example 1.

**Failed output:**

**Subject:** Your Gold Member Exclusive: Free Gear Repair + Early Sale Access

**Body:**

We've noticed it's been a while since your last visit, and we'd love to welcome you back to NorthStar Retail.

As a valued Gold member, you already enjoy some great perks—like free standard shipping on all orders and free return shipping. To say thank you for your loyalty, we're giving you an extra boost:

**Claim your bonus gear repair service** — Bring in any outdoor or footwear item for professional repair at no charge. Gold members receive 2 free repairs per year, and we want to make sure you're using this benefit.

**Plus, get 24-hour early access to our upcoming sales** — Shop outdoor and footwear deals before everyone else.

This offer is valid for 45 days. Simply reply to this email or visit your account to activate.

We're here to support your adventures. Let's get you back out there.

**Rationale:**

The customer is a high-value Gold member (LTV $3,120) with 81% churn probability and 47 days since last purchase. The offer leverages **existing Gold tier benefits** that are documented in the policy context: free gear repair (2 per year) and 24-hour early sale access. These are not new incentives—they're underutilized benefits designed to re-engage the member. The offer respects the 45-day validity window and one-active-offer-per-member rule. No discounts, higher-tier benefits, or unsupported promotions are claimed. The messaging is personalized to their top categories (Outdoor, Footwear) and online preference without inferring a tier change based on lifetime value.

**Why it failed:** It called existing Gold benefits an exclusive “extra boost” and “bonus” offer, then invented redemption instructions (reply or activate in the account). The rationale itself admits these are existing benefits, not new incentives.

**Fix:** Tighten the generation instructions so the model may remind customers of verified existing benefits, but must not present them as newly granted promotions or invent activation steps, codes, or offer mechanics. The later Gold answer in Example 1 uses the benefits as reminders and does not invent a redemption process.

### Failure 2: Unsupported claim that a purchase maintains Gold status

**Retrieved chunk IDs:** `POL-LOY-011-s010-c001`, `KB-FAQ-022-s003-c001`, `KB-FAQ-022-s003-c002`, `POL-LOY-011-s013-c001`, `POL-LOY-011-s012-c001`, `POL-RET-004-s007-c001`.

**Input:** Same customer context and question as Example 1.

**Failed output:**

**Subject:** Your Gold Benefits Are Waiting—Free Shipping & Easy Returns on Your Next Order

**Body:**

We've noticed it's been a while since your last visit, and we'd love to have you back. As a Gold member, you're already enjoying free standard shipping on every order and free return shipping—benefits that make shopping for outdoor gear and footwear hassle-free. Your 1.5× points earn rate also means you're building rewards faster on every purchase. Come back soon and take advantage of these existing membership perks, plus early access to sales 24 hours before the general public. Shop now and keep your Gold status strong.

**Rationale:**

The customer has a high churn probability (0.81) and hasn't purchased in 47 days, putting them at immediate risk of lapsing. The retrieved policy context does not support a new discount, bonus points, or spending incentive—only existing tier benefits are documented. The rationale focuses on Gold-tier benefits explicitly listed in the policy (free standard shipping, free return shipping, 1.5× points earn rate, and 24-hour early access to sales) that align with the customer's profile (online shopping, outdoor and footwear categories). No false urgency, expiration date, or invented promotion is included. The message reminds the customer of concrete, existing value to encourage re-engagement without violating the constraint against inferring unsupported incentives.

**Why it failed:** “Keep your Gold status strong” implies that shopping is needed to retain Gold status. The customer context and retrieved policy did not establish that claim.

**Fix:** Remove status-maintenance language and avoid suggesting that a purchase preserves or changes a tier unless the policy and customer data support it. The later Gold answer in Example 1 invites the customer back without making a status-retention claim.
