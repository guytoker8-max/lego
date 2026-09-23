# Supplier Research: brick kits made from customer photos (dropship / print-on-demand)

**Date:** 2026-09-23
**Scope:** Desk research from public web pages only. I contacted no one and created no accounts. "Unverified" means I could not confirm the point on a page the company controls.
**Assumed business model:** The customer pays us. A supplier picks the loose LEGO-compatible bricks, adds our printed instruction booklet and ships everything to the customer. We hold little or no stock. The company is probably based in Israel and may ship internationally.

---

## 1. Executive summary

- **No brick supplier I found publishes an API for placing buyer orders.**
  - The BrickLink API can read and update orders. With `direction=out` it can list orders you placed as a buyer. It has no call that creates an order or a cart.
  - The Brick Owl API can build a cart from a parts list, but a person must finish checkout in a browser.
  - The Rebrickable API covers the catalog and user collections only. Its terms allow commercial use.
  - The LEGO Shop is for consumers only and forbids resale. I found no public Pick a Brick API.
  - The only GoBricks "API" I found (on gobricks.cn) was reverse-engineered by a third party. It is not an official API.
  - **Consequence:** at launch, orders will be sent as files, by email or through a web portal. The software should produce a standard parts list (BrickLink XML or a Studio/Rebrickable CSV) and send it as a package that a person can check.
- **Only one supplier publicly offers the full service we need: Wobrick.** Wobrick describes itself as the "exclusive overseas agent for Gobricks". It advertises all of the following:
  - no minimum order for most projects
  - custom instruction manuals
  - private-label packaging
  - "Dropshipping and bulk fulfillment"
  - parts lists accepted by email or WhatsApp
  - a catalog numbered with LEGO/BrickLink design IDs
- **Genuine-LEGO options exist but are expensive and manual.** BrickLink, Brick Owl, LEGO Pick a Brick, BuildaMOC and MOCHUB all use genuine LEGO parts. They cost more, and a single order may be split across several sellers. They suit a premium tier, not the default product.
- **Factories that build kits to order (OEM) only make sense at volume.** The official Xingbao site offers printed manuals, private label and "500 prototype sets" up to 50,000+ units. Sourcing guides put custom packaging at 500 to 2,000 sets and new moulds at 5,000+ sets.

### Recommended integration order
1. **Rebrickable API: catalog and ID mapping only (build first).** Commercial use is allowed. We use it to normalise part and colour IDs (BrickLink, LEGO element ID, Brick Owl) in our generator, so any supplier export is clean. It places no orders.
2. **Wobrick: first supplier to connect.** This means:
   - generating a parts list in BrickLink XML or a Studio/Rebrickable-compatible file
   - sending a PDF of the booklet with it
   - submitting by email, reviewed by a person
   - running a test order before promising lead times to customers

   Wobrick is first because it is the only supplier that publicly offers dropship, private label and custom manuals with no minimum order.
3. **Webrick / Brickwith: second GoBricks channel and price benchmark.** It is GoBricks' own storefront. It has 30,000+ parts, no minimum order, ships within 3 business days, and accepts BrickLink XML uploads. Its "Custom Kits" page mentions "Part List-based packing". Its dropship and booklet-insert support are unverified.
4. **Marstoy: backup GoBricks dropship option.** It has a published pricing formula and a lead time of at least 5 business days. Blind shipping and booklet inserts are unverified.
5. **Later, at volume:**
   - a Shantou OEM (Xingbao) for fixed-design kits, or
   - our own bulk stock at a warehouse that offers an order API, if the product uses a small, fixed set of parts (for example photo mosaics made of 1×1 plates or tiles plus baseplates). ShipBob is one such warehouse.
6. **Do not automate BrickLink or Brick Owl purchasing.** Neither offers checkout through an API. Both are LEGO-only, and orders split across several shops. Use them only to source samples or for a manual premium tier.

---

## 2. Comparison table

| Company | Category | API | Buyer ordering via API? | Dropship | Blind ship / private label | Minimum order | Pricing signal | Confidence |
|---|---|---|---|---|---|---|---|---|
| **Wobrick** (GoBricks agent) | Wholesaler + kit fulfilment | None found | No (email or WhatsApp parts list; retail web shop) | **Yes (stated)** | Private label packaging + custom manuals stated; unmarked shipping without prices/invoice unverified | None "for most projects" | Catalog prices from about $0.07 to $0.42 per part | Medium |
| **Webrick / Brickwith** (GoBricks official) | Wholesaler (loose parts) | None official; gobricks.cn API is reverse-engineered | No (web upload of BrickLink XML / Studio / Rebrickable files) | Unverified | Unverified | None | GoBricks own shop: 3001 ×100 = $15.19 (≈$0.15/pc) | Medium |
| **Marstoy** (GoBricks dropship) | Dropship reseller | None found | No (email quote) | Yes (stated as "Gobricks dropshipping") | Unverified | Unverified | GoBricks price ÷ exchange rate ÷ 0.94 | Medium-low |
| **GoBricks** (factory) | Manufacturer | None official | No | Through Webrick/Brickwith/Wobrick | Unverified | Unverified | Retail bulk bags: ≈$0.04 to $0.15/pc | Medium |
| **Xingbao** | OEM kit manufacturer | None | No (email/WhatsApp) | Not stated | Private label + printed manuals: yes | 500 prototype sets; 50,000+ for mass production | Per-set quote only | Medium |
| **Wange** | OEM manufacturer | None found | No | Unverified | Unverified | Unverified | Unverified | Low |
| **BrickLink** | Marketplace (genuine LEGO) | Seller-side store API (OAuth 1.0) | **No** (read/update only; `direction=out` lists buyer orders) | Not applicable | Not applicable | Varies by seller | Varies by seller | High (API); low (terms) |
| **Brick Owl** | Marketplace (genuine LEGO) | Catalog + seller API (API key) | **Partly:** `cart_basic` builds a cart; checkout is manual in a browser | Not applicable | Not applicable | Varies by seller | Varies by seller | High |
| **Rebrickable** | Catalog data | Catalog + user collections | No | Not applicable | Not applicable | Not applicable | Free; commercial use allowed | High |
| **LEGO Pick a Brick** | First-party parts shop | None found | No; consumer-only, no resale | No | No | Many parts capped at 10 or 100 per order | Unverified | High (terms) |
| **BuildaMOC** | Kit fulfilment (genuine LEGO) | None found | No (quote form) | Yes (direct-to-customer) | Branded packaging + printed instructions | Unverified | Quote only | Medium |
| **MOCHUB** | Kit marketplace (genuine LEGO) | None mentioned | No | Yes (it ships to buyers) | No (it is their marketplace) | Not applicable | Takes 30% | Medium |
| **Letbricks** | Parts sourcing + B2B kits | None found | No (email) | Not stated | Custom packaging "pending feasibility" | Not stated | Quote only | Low |
| **United Bricks / custombrickprinting** | Custom printing | None | No | Not applicable | Not applicable | 250 per design (United Bricks); packs of 100 | $250 per 100 printed 2×4 bricks (≈$2.50 each) | Medium |
| **ShipBob** | General warehouse (3PL) with kitting | **Yes: Create Order API** | Yes, for stock *we* keep there | Yes | Yes (inserts at packing) | Unverified | Quote only | Medium |

---

## 3. Per-company details

### 3.1 LEGO-compatible brick wholesalers

#### Wobrick: exclusive overseas agent for GoBricks
- **Relationship to GoBricks:** "As the exclusive overseas agent for Gobricks, Wobrick is to provide superior quality…" ([wobrick.com](https://wobrick.com/)). A Eurobricks forum thread (Nov 2023) calls it "a partner of Gobricks" ([Eurobricks](https://www.eurobricks.com/forum/forums/topic/196076-alternative-to-selling-gobricks-parts-since-webrick-cant-wobrick/)).
- **Custom kit service** ([MOC Customization](https://wobrick.com/moc-customization/)):
  - The customer sends the parts list by email or WhatsApp.
  - No minimum order: "There is no minimum order quantity for most projects."
  - Offers "Custom Instruction Manuals", "Private Label Packaging", branded boxes and polybags, and UV printing of logos on bricks.
  - "Dropshipping and bulk fulfillment available."
  - Preparation takes 10 to 15 business days. In-stock items take about 5 working days; out-of-stock items take about 15 days.
  - Catalog of 30,000+ parts in 70+ standard colours.
  - Prices are quoted per project.
- **Shipping** ([Shipping & Delivery](https://wobrick.com/shipping-delivery/)):
  - Processing takes 5 to 7 working days.
  - 4PX airline takes about 7 to 15 business days. FedEx takes 5 to 7 business days for parcels over 3 kg.
  - Free shipping over $20; $3 fee below that. An EU surcharge of $3.50 applies.
  - Customs duties are not included.
  - No country list is published. **Israel is unverified.**
- **Part numbering:** Catalog items carry LEGO/BrickLink design numbers, for example "Spoiler, Plate Special 1 x 2 #30925" and "Bar 1 x 4 x 2 #6187". Listed prices start at about $0.07 to $0.42 per part ([category page](https://wobrick.com/product-category/brick/gobricks-bricks/)). The upload tool accepts Studio, BrickLink and Rebrickable formats ([wobrick.com](https://wobrick.com/)).
- **API:** None found (unverified).
- **Unmarked shipping:** "Private label" is stated. Shipping without prices, an invoice or Wobrick branding is **unverified**.

#### Webrick, now Brickwith: GoBricks' official platform
- **Rebrand:** webrick.com now says "Webrick is now brickwith.com". Brickwith calls itself the "Gobricks Official Shop" ([webrick.com](https://www.webrick.com/), [brickwith.com](https://www.brickwith.com/en)).
- **Ownership:** A forum post from June 2024 reports that "Webrick was acquired by Gobricks" and sells GoBricks parts only ([Eurobricks](https://www.eurobricks.com/forum/forums/topic/196076-alternative-to-selling-gobricks-parts-since-webrick-cant-wobrick/)).
- **Catalog and stock:** 30,000+ parts, no minimum order, factory-direct pricing. It describes itself as "the world's only official platform for Gobricks" ([Webrick blog](https://www.webrick.com/blog/post/how-webrick-ends-out-of-stock-for-brick-buyers)).
- **Shipping** ([shipping guide](https://www.webrick.com/shipping-guide.html)):
  - Orders ship within 3 business days.
  - Standard delivery takes 7 to 20 days. DHL/FedEx express takes 3 to 7 days for orders over $300.
  - Free shipping over $25.
  - Restocking takes 5 to 10 days, and split shipments are free.
  - The country list and Israel are **unverified**.
- **Uploads:** Accepts Studio (.ldr/.csv/.xml), LDD (.lxf), BrickLink XML, Rebrickable CSV/XML and xlsx, with a stated "over 90% match rate" ([webrick.com](https://www.webrick.com/)).
- **Custom Kits page:** Its meta description reads "Source brick parts for custom kits and MOCs with no minimum quantity and Part List-based packing". The rest of the page is rendered by JavaScript and I could not read its details ([Brickwith Custom Kits](https://www.brickwith.com/en/solutions/custom-kits)). Dropship, unmarked shipping and booklet inserts are **unverified**.
- **Bulk products:** Random packs, 10-piece packs and 1 kg packs ([bulk bricks](https://www.webrick.com/bulk-bricks)). No prices were visible.
- **API:** None official. A third-party GitHub project uses `gobricks.cn/frontend/v1/community/lego2ItemList` and labels it "inofficial / reverse engineered" ([GoBricksPart-API](https://github.com/mnemocron/GoBricksPart-API)). **Do not build on it.**

#### GoBricks: the factory
- Says it makes all parts in its own factory, with "2,000+ own molds, 50+ colors" ([gobricks.net](https://gobricks.net/)). Brickwith claims 30 million bricks a day ([Webrick blog](https://www.webrick.com/blog/post/how-webrick-ends-out-of-stock-for-brick-buyers)).
- **Part numbering:** GoBricks uses its own "GDS-" numbers, which map to LEGO IDs. Examples from listing titles in web search results: GDS-542 = 3001 (Brick 2×4), GDS-501 = 3024 (Plate 1×1), GDS-511 = 3020 (Plate 2×4). I could not open the Amazon pages themselves.
- **Retail bulk prices** on the GoBricks shop ([mygobricks.com bulk](https://mygobricks.com/collections/bulk-bricks)):

  | Part | Pack | Price | Per piece |
  |---|---|---|---|
  | Brick 2×4 #3001 | 100 | $15.19 | ≈$0.15 |
  | #32607 | 900 | $34.20 | ≈$0.038 |
  | #22890 | 500 | $22.55 | ≈$0.045 |

- Wholesale price lists are **unverified**.

#### Xingbao: kit manufacturer that builds to order (OEM)
- Official site offering OEM/ODM ([xingbao.org](https://xingbao.org/)):
  - "Printed instruction manual design", "Private label packaging", assembly and labelling.
  - Minimum order from "500 prototype sets up to 50,000+ unit mass production".
  - 4,000+ moulds, 320 moulding machines, CE and ISO 9001 certification.
  - Based in Chenghai, Shantou.
- Dropship and loose-part sales are not stated.
- It suits fixed designs at volume, not one-off kits generated from photos.

#### Wange
- Shantou manufacturer listed on Made-in-China ([showroom](https://www.made-in-china.com/showroom/wangeblocks/)) and Alibaba ([supplier page](https://www.alibaba.com/supplier/wange-technology-industrial-co-lego.html)). I did not read their terms. Minimum order, private label and loose-part sales are all **unverified**.

#### Generic Alibaba / 1688 OEM benchmarks
- Alibaba listing pages are rendered by JavaScript and I could not read them.
- One sourcing agent publishes these ranges ([Jingsourcing](https://jingsourcing.com/p/building-blocks-from-china/)):
  - loose compatible bricks "about $10/kg"
  - custom colour box and logo on an existing model: about 2,000 sets
  - packaging only: 500 to 1,000 sets
  - new moulds: 5,000+ sets and "a few thousand USD per mold"
  - production about 30 days; samples 7 to 10 days
  - instruction booklets, UV printing and private label are all available
- These are one agent's figures, not supplier quotes.

### 3.2 Brick marketplaces and data APIs

#### BrickLink: API is for sellers
- **API:** OAuth 1.0 using a consumer key/secret plus token/secret, obtained by logging in with a BrickLink account ([BrickLink API wiki](https://static.bricklink.com/alpha/default/api_wiki.html)).
- **Order calls:** GET `/orders`, GET `/orders/{id}` (plus items, messages, feedback), PUT `/orders/{id}` and PUT `/orders/{id}/status`.
  - In Get Orders, `direction` = `"in"` returns orders you received as a seller; `"out"` returns orders you placed.
  - **There is no call that creates an order or a cart.** A buyer can read their purchases through the API but cannot place them.
- **Other resources:** inventory, catalog, price guide, coupons, member notes, feedback, shipping methods and element-ID mapping ([Store API changelog](https://www.bricklink.com/v2/api/welcome.page)).
- **Terms:** I could not read the rules on automated purchasing, drop-shipping or commercial buyers. BrickLink help pages returned HTTP 405/403 ([ToS](https://help.bricklink.com/hc/en-us/articles/360034787873-Terms-of-Service)). **Unverified.**
- **Parts:** Genuine LEGO. Seller stores ship separately.

#### Brick Owl: catalog and seller API; carts only for buyers
- **API** ([Brick Owl API docs](https://www.brickowl.com/api_docs)):
  - Authenticated with an API key.
  - 600 requests/min, or 100/min for bulk calls.
  - Endpoint groups: catalog (lookup, pricing, availability), inventory, orders, invoices, wishlists, addresses.
  - `/v1/catalog/id_lookup` maps design IDs, LEGO item numbers and BrickLink numbers to Brick Owl IDs.
- **Buyer side:**
  - `POST /v1/catalog/cart_basic` takes `design_id`, `color_id` and `qty`, plus condition and country. It returns a cart ID that the user opens at `/catalog_cart_load/ID` **and checks out in a browser**. It requires "Catalog Approval".
  - Store `addtocart` and `addtowishlist` are form posts.
  - The order endpoints are for sellers.
  - **There is no API checkout.**
- **Catalog cart behaviour:** It spreads a parts list across up to 5 stores, and "orders will be shipped separately by the different stores" ([Catalog Cart](https://www.brickowl.com/catalog_cart)). One kit would arrive as up to 5 parcels, so it cannot ship as one package with our booklet.
- "We only permit the sale of official LEGO® items on Brick Owl" ([buying guide](https://www.brickowl.com/help/buying-lego-parts)).

#### Rebrickable: catalog only
- **API** ([Rebrickable API](https://rebrickable.com/api/)):
  - covers parts, colours, sets, set inventories, external IDs (BrickLink, LEGO element) and user collections
  - has **no ordering**
  - requires an API key
- **Terms:** "The Rebrickable API may be used for any purpose, including commercial." Attribution is appreciated but not required ([Rebrickable terms](https://rebrickable.com/terms/)).
- Rate limits were not stated on the pages I read.

#### LEGO Pick a Brick / Bricks & Pieces
- **Resale:** "The LEGO Shop is intended for consumers to purchase items for personal use, not for resale or commercial use." LEGO may cancel orders at its discretion. Placing multiple orders to get around limits is grounds for cancellation. A "large order" means more than 999 of any single piece and needs customer service ([LEGO T&C](https://www.lego.com/en-us/page/terms-and-conditions)).
- **Order caps:** Since 2025, about 6,400 standard elements in North America are capped at 10 per order. In Europe, 7,021 elements are capped at 10 and 254 at 100 ([New Elementary](https://www.newelementary.com/2025/03/pick-brick-usa-canada-standard-elements.html)).
- **API:** None found.
- **Verdict:** Not usable as a supplier for a reselling business.
- **Israel:** Delivery is unverified. Forwarding services advertise LEGO-to-Israel delivery ([example](https://www.easy-delivery.com/en/delivery/lego/israel)), which suggests LEGO.com does not ship there directly.

### 3.3 Custom brick manufacturers (printing and moulding)
- **United Bricks (UK):**
  - Bespoke printing on genuine LEGO heads, torsos, bricks and tiles.
  - Minimum 250 per design for full minifigures; smaller for single components.
  - Priced by quote. Contact info@unitedbricks.com ([United Bricks](https://www.unitedbricks.com/bespoke-printing)).
- **custombrickprinting.com / minifigco:**
  - 100 compatible 2×4 bricks with a logo cost $250 (front) or $400 (front and back).
  - Contact sales@minifigco.com ([product page](https://custombrickprinting.com/products/customized-logo-bricks)).
- **Wobrick** also offers UV printing on GoBricks parts ([MOC Customization](https://wobrick.com/moc-customization/)).
- **New moulds:** Contract moulding in China costs "a few thousand USD per mold" and needs 5,000+ sets ([Jingsourcing](https://jingsourcing.com/p/building-blocks-from-china/)).
- **Relevance:** Printing and moulding matter only for extras such as a printed name tile or a logo brick. The core kits use standard parts.

### 3.4 Dropshipping and fulfilment
- **Wobrick:** see 3.1. The best public match for our model.
- **Marstoy "Gobricks dropshipping"** ([Marstoy](https://marstoy.com/pages/gobricks-dropshipping)):
  - Upload the list to GoBricks, convert it, then send the file to Marstoy for a quote.
  - Price = GoBricks price ÷ exchange rate ÷ 0.94, excluding shipping.
  - "Usually no less than 5 business days".
  - Contact support@marstoy.net.
  - Unmarked shipping, booklet inserts and minimum order are **unverified**.
- **BuildaMOC** (Spain, with a Delaware entity) ([About](https://buildamoc.com/pages/about)):
  - "100% original LEGO® elements".
  - Custom printed instructions and branded packaging.
  - Ships direct to customers worldwide.
  - Business quotes through a form.
  - A premium genuine-LEGO option for later.
- **MOCHUB** ([Brickset article](https://brickset.com/article/52089/mochub-takes-the-hard-work-out-of-buying-and-selling-mocs)):
  - A marketplace for genuine LEGO kits; the designer gets 70%.
  - Ships worldwide in 9 to 13 business days.
  - It sells under its own marketplace, not our brand, so it does not fit.
- **Letbricks:** parts sourcing and B2B kits; custom packaging "pending technical feasibility"; contact service@letbricks.com ([Letbricks](https://www.letbricks.com/parts-customization/)). Details are thin.
- **ShipBob (general 3PL):**
  - Kitting either ahead of time or at packing time, with inserts added per order.
  - Kitting sites in Chicago, Dallas, Pennsylvania and Los Angeles ([ShipBob kitting](https://www.shipbob.com/ecommerce-fulfillment/kitting-assembly/)).
  - A documented Create Order API ([ShipBob API](https://developer.shipbob.com/api/orders/create-order)) and a Netherlands site ([support](https://support.shipbob.com/s/article/ShipBob-Fulfillment-in-the-Netherlands)).
  - Viable only if we hold bulk stock of a *small, fixed* set of parts and colours.
  - Risk: picking hundreds of loose pieces per order at per-unit fees will be costly. **Get a quote first.**

### 3.5 Bulk brick suppliers
- **GoBricks shop:** bulk bags per part, for example 3001 ×100 for $15.19 ([mygobricks bulk](https://mygobricks.com/collections/bulk-bricks)).
- **Webrick/Brickwith:** 1 kg packs and 10-piece packs ([bulk](https://www.webrick.com/bulk-bricks)).
- **Chinese mixed bulk:** about $10/kg according to a sourcing agent ([Jingsourcing](https://jingsourcing.com/p/building-blocks-from-china/)).
- **Amazon:** 1,000-piece 1×1 plate and tile packs sold for mosaics, including GoBricks-branded packs. Seen in search results only; prices unverified.

### 3.6 Trademark: what we must avoid
Rules from LEGO's Fair Play policy ([LEGO Fair Play](https://www.lego.com/en-us/legal/notices-and-policies/fair-play)):
- If "LEGO" is used at all, use it only as an adjective, always with ®.
- Never write "LEGOs".
- Never put LEGO in a domain name.
- **Never use the LEGO logo** on an unofficial site.
- Set the word in the same typeface as the surrounding text.
- Add a disclaimer: "LEGO® is a trademark of the LEGO Group of companies which does not sponsor, authorize or endorse this site." LEGO notes that a disclaimer "will not serve to undo an improper trademark use".

Background:
- The EU refused the 2×4 brick shape as a trademark. LEGO has since registered design rights, from 2021, and relies on copyright, trademark and design law together ([Dennemeyer](https://www.dennemeyer.com/blog/posts/everyday-ip-the-building-blocks-of-lego-law)).

What this means for us (not legal advice; get local counsel):
- Keep "LEGO" out of the brand name, domain, logo, product titles and ads.
- Describe kits as "compatible bricks" or "compatible with major brick brands". A plain factual compatibility statement with ® and the disclaimer is the most we should use.
- Do not use LEGO box art, fonts or minifigure images.
- Do not call a kit a "LEGO set".

---

## 4. Open questions to ask suppliers

1. **Ordering channel:** Is there any API, SFTP drop or bulk-order upload we can call per order? If not, what file format and what turnaround for a manual quote (BrickLink XML, Studio .io, CSV with BrickLink IDs)?
2. **Part and colour IDs:** Is the catalog keyed by BrickLink/LEGO design ID and BrickLink colour ID? How do they map to GDS numbers? What is the match rate for a typical 300 to 1,500 part list?
3. **Booklet insert:** Can they print our instruction booklet from a PDF (size, pages, binding, colour, cost)? Or can they insert booklets we send them in bulk?
4. **Unmarked shipping:** Can parcels go out with our return address and branding, no supplier logo, and no price invoice inside? What goes on the customs declaration?
5. **Shipping to Israel:** Available carriers, delivery times and whether duties/VAT can be prepaid. The same questions for EU (IOSS) and US.
6. **Per-order kits:** Is there a minimum per order or per SKU? Is there a per-order fee on top of part prices?
7. **Pricing:** Is there a wholesale or partner price list for 1×1 plates/tiles, and at what volume?
8. **Stock-outs:** How do they handle missing parts? Colour substitution rules, partial shipments, and how quickly they notify us.
9. **Quality and packing:** Parts bagged by step or by colour? Weight check or QC photo per order? What is the missing-part rate and replacement policy?
10. **Commercial rights:** Written confirmation that we may resell their parts in our branded kits. Is any GoBricks co-branding required?
11. **Payment and terms:** Invoicing per order or monthly? Currencies? Bank transfer versus PayPal (Marstoy adds 4 to 6%)?
12. **Capacity and service levels:** Orders per day, peak season (Q4) lead times, and holiday shutdowns (Chinese New Year).
13. **BrickLink** (if a genuine-LEGO tier is ever added): Is drop-shipping to a customer's address allowed under the current terms? Are automated or semi-automated purchases allowed? I could not read these terms.
