const puppeteer = require('puppeteer');
const fs = require('fs');

// --- CONFIGURATION ---
const OUTPUT_FILE = 'Final_Clean_Data_CS.txt';
// We focus on Massey first to ensure success
const TARGET_URL = "https://cpq.agcocorp.com/masseyferguson/customer/en_gb/wholegoods/products";

// --- SELECTORS ---
const SELECTORS = {
    // Cookie Banner (The Enemy)
    cookieBanner: '#onetrust-banner-sdk, .truste_box_overlay, .cookie-banner, #trustarc-banner',

    // Grid Items (Categories & Products)
    gridItem: '.product-item, .category-tile, .card, div[class*="tile"], div[class*="product"]',

    // Data Extraction
    // We ignore the first H1 if it looks like a banner
    title: 'h1.product-title, h1.title, .hero-text h1',
    desc: '.description, .product-description, #description',
    specs: '.specifications, table.tech-specs'
};

(async () => {
    console.log("=================================================");
    console.log("   SAP CPQ 'DEEP DRILL' SCRAPER - ADMIN: CS");
    console.log("=================================================");

    fs.writeFileSync(OUTPUT_FILE, "BRAND;CATEGORY;PRODUCT;DESCRIPTION;SPECS\n"); // CSV-like Header

    const browser = await puppeteer.launch({
        headless: false,
        defaultViewport: null,
        args: ['--start-maximized']
    });

    const page = await browser.newPage();
    page.setDefaultNavigationTimeout(0); // Infinite timeout

    console.log(`[1] Navigating to Massey Ferguson Catalog...`);
    await page.goto(TARGET_URL, { waitUntil: 'domcontentloaded' });
    await waitForAngular(page);

    // --- PHASE 1: KILL COOKIES ---
    await killCookieBanner(page);

    // --- PHASE 2: GET CATEGORIES (Level 1) ---
    // e.g., Tractors, Combines, Balers
    const categories = await getGridItems(page);
    console.log(`>>> Found ${categories.length} Main Categories.`);

    for (let i = 0; i < categories.length; i++) {
        // RE-FRESH DOM
        await killCookieBanner(page);
        const currentCats = await getGridItems(page);
        const catElement = currentCats[i];

        if (!catElement) continue;

        const catName = await page.evaluate(el => el.innerText.split('\n')[0], catElement);
        console.log(`\n=== ENTERING CATEGORY: ${catName} ===`);

        // CLICK LEVEL 1
        await catElement.click();
        await waitForAngular(page);
        await killCookieBanner(page); // Kill it again if it reappears

        // --- PHASE 3: GET PRODUCTS (Level 2) ---
        // e.g., MF 4700, MF 5700
        const products = await getGridItems(page);
        console.log(`   >>> Found ${products.length} Series/Products in ${catName}.`);

        for (let j = 0; j < products.length; j++) {
            const currentProds = await getGridItems(page); // Refresh DOM
            const prodElement = currentProds[j];

            if (!prodElement) continue;

            const prodName = await page.evaluate(el => el.innerText.split('\n')[0], prodElement);
            console.log(`      [${j+1}/${products.length}] Scraping: ${prodName}`);

            // CLICK LEVEL 2 (Enter Product Detail)
            await prodElement.click();

            // Wait for Title (Ensure we are on detail page)
            try {
                await page.waitForSelector('h1', { timeout: 10000 });
            } catch(e) {}

            // SCRAPE
            const data = await page.evaluate(() => {
                const getT = (s) => document.querySelector(s)?.innerText.replace(/\s+/g, ' ').trim() || "";
                // Try specific title first, fallback to generic h1, ignore generic words
                let t = getT('h1.product-title');
                if (!t) t = getT('h1');
                if (t.includes("PRIVACY") || t.includes("Cookie")) t = "Unknown Product";

                return {
                    t: t,
                    d: getT('.description') || getT('#description'),
                    s: getT('.specifications')
                };
            });

            // SAVE TO FILE
            // Format: Massey Ferguson || Tractors || MF 4700 || Desc... || Specs...
            const safeRow = `Massey Ferguson||${catName}||${data.t}||${data.d}||${data.s}\n`;
            fs.appendFileSync(OUTPUT_FILE, safeRow);
            console.log(`      [SAVED] ${data.t}`);

            // GO BACK TO LEVEL 2 LIST
            await page.goBack({ waitUntil: 'domcontentloaded' });
            await waitForAngular(page);
            await new Promise(r => setTimeout(r, 1000));
        }

        // GO BACK TO LEVEL 1 LIST (Main Catalog)
        console.log(`=== FINISHED CATEGORY: ${catName}. Going up... ===`);
        await page.goBack({ waitUntil: 'domcontentloaded' });
        await waitForAngular(page);
        await new Promise(r => setTimeout(r, 2000));
    }

    console.log("\nDONE! Run the Python script now.");
    await browser.close();
})();

// --- HELPERS ---

async function getGridItems(page) {
    // Wait for grid
    try {
        await page.waitForSelector(SELECTORS.gridItem, { timeout: 5000 });
    } catch(e) {}
    return await page.$$(SELECTORS.gridItem);
}

async function waitForAngular(page) {
    try {
        await page.waitForSelector('.loader', { hidden: true, timeout: 5000 });
    } catch(e) {}
    await new Promise(r => setTimeout(r, 1500)); // Pause for rendering
}

async function killCookieBanner(page) {
    await page.evaluate((sel) => {
        const banners = document.querySelectorAll(sel);
        banners.forEach(b => b.remove()); // Delete it from DOM
    }, SELECTORS.cookieBanner);
}