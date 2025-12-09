const puppeteer = require('puppeteer');
const fs = require('fs');

// --- CONFIGURATION ---
const TARGET_URL = "https://cpq.agcocorp.com/masseyferguson/customer/en_gb/wholegoods/products";
const OUTPUT_FILE = 'Massey_Data_Clean.json';

const SELECTORS = {
    // Broad selectors to catch ANY type of tile
    gridTile: '.product-item, .category-tile, .card, div[class*="tile"], div[class*="product"], app-category-card',

    // Cookie Banners to destroy
    overlays: '#onetrust-banner-sdk, .truste_box_overlay, .cookie-banner, .modal-backdrop, .cdk-overlay-container'
};

(async () => {
    console.log("------------------------------------------------");
    console.log("   SAP CPQ SCRAPER V2 (SMART WAIT EDITION)");
    console.log("------------------------------------------------");

    const browser = await puppeteer.launch({
        headless: false,
        defaultViewport: null,
        args: ['--start-maximized']
    });

    const page = await browser.newPage();
    page.setDefaultNavigationTimeout(0); // No timeout

    // 1. NAVIGATE
    console.log(`[1] Navigating to Catalog...`);
    await page.goto(TARGET_URL, { waitUntil: 'domcontentloaded' });

    // 2. NUKE BANNERS (Immediate CSS Injection)
    await page.addStyleTag({ content: `${SELECTORS.overlays} { display: none !important; visibility: hidden !important; pointer-events: none !important; }` });

    // 3. SMART WAIT (The Fix)
    console.log("    ...Waiting for grid text ('TRACTORS') to appear...");
    try {
        // Wait up to 30s for the specific text that confirms the grid is ready
        await page.waitForFunction(() =>
            document.body.innerText.includes("TRACTORS") ||
            document.body.innerText.includes("COMBINES"),
            { timeout: 30000 }
        );
        console.log("    >>> GRID DETECTED!");
    } catch (e) {
        console.log("    !!! TIMEOUT: Grid didn't load. Saving screenshot...");
        await page.screenshot({ path: 'debug_failure.png' });
        console.log("    (Check 'debug_failure.png' to see what happened)");
        await browser.close();
        return;
    }

    // 4. GET CATEGORIES
    const categoryNames = await getTileNames(page);
    console.log(`>>> Found Categories: ${categoryNames.join(', ')}`);

    let allData = [];

    // --- LOOP CATEGORIES ---
    for (const catName of categoryNames) {
        if (catName.toUpperCase().includes("PRIVACY") || catName.length < 3) continue;

        console.log(`\n=== PROCESSING: ${catName} ===`);

        // A. Click Category
        const clicked = await clickTileByText(page, catName);
        if (!clicked) continue;

        // B. Wait for Products (Look for "Series" or "MF")
        await new Promise(r => setTimeout(r, 4000));
        await page.addStyleTag({ content: `${SELECTORS.overlays} { display: none !important; }` });

        // C. Get Products
        const productNames = await getTileNames(page);

        // Validating we actually moved
        if (JSON.stringify(productNames) === JSON.stringify(categoryNames)) {
            console.log("    (Navigation failed, still on main menu. Skipping.)");
            continue;
        }

        console.log(`    >>> Found Products: ${productNames.length} items`);

        // --- LOOP PRODUCTS ---
        for (const prodName of productNames) {
            // Filter noise
            if (prodName.includes("Back") || prodName.includes("Privacy")) continue;

            console.log(`       -> Scraping: ${prodName}`);

            const prodClicked = await clickTileByText(page, prodName);
            if (!prodClicked) continue;

            // Wait for Details (H1)
            try { await page.waitForSelector('h1', { timeout: 8000 }); } catch(e) {}

            // Scrape
            const data = await page.evaluate(() => {
                const txt = (s) => document.querySelector(s)?.innerText.trim() || "";
                return {
                    name: txt('h1'),
                    desc: txt('.description') || txt('#description'),
                    specs: txt('.specifications') || txt('table')
                };
            });

            if (data.name) {
                console.log(`          [OK] ${data.name.substring(0, 30)}...`);
                allData.push({
                    brand: "Massey Ferguson",
                    category: catName,
                    product: data.name,
                    description: data.desc,
                    specs: data.specs
                });
            }

            // Back to Product List
            await page.goBack();
            await new Promise(r => setTimeout(r, 2000));
            await page.addStyleTag({ content: `${SELECTORS.overlays} { display: none !important; }` });
        }

        // Back to Main Menu
        console.log(`    (Returning to Categories...)`);
        await page.goto(TARGET_URL, { waitUntil: 'domcontentloaded' });
        await new Promise(r => setTimeout(r, 3000));
        await page.addStyleTag({ content: `${SELECTORS.overlays} { display: none !important; }` });
    }

    fs.writeFileSync(OUTPUT_FILE, JSON.stringify(allData, null, 2));
    console.log(`\nDONE! Saved to ${OUTPUT_FILE}`);
    await browser.close();
})();

// --- HELPERS ---
async function getTileNames(page) {
    return await page.evaluate((sel) => {
        const tiles = Array.from(document.querySelectorAll(sel));
        return tiles.map(t => t.innerText.split('\n')[0].trim()).filter(t => t.length > 0);
    }, SELECTORS.gridTile);
}

async function clickTileByText(page, text) {
    return await page.evaluate((sel, txt) => {
        const tiles = Array.from(document.querySelectorAll(sel));
        const target = tiles.find(t => t.innerText.includes(txt));
        if (target) {
            target.click();
            return true;
        }
        return false;
    }, SELECTORS.gridTile, text);
}