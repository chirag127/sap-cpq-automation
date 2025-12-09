const puppeteer = require('puppeteer');
const fs = require('fs');

// --- CONFIGURATION ---
const BASE_URL = 'https://cpq.agcocorp.com/agco/customer/en_GB/configurator';
const OUTPUT_FILE = 'agco_full_dump.json';
const MAX_DEPTH = 6; // Safety stop

// --- STATE ---
let fullData = [];
let visitedUrls = new Set();

// ==========================================
// 1. GLOBAL HELPER FUNCTIONS (Moved Outside)
// ==========================================

/**
 * Waits for the Angular ".loader-container" to disappear.
 * Based on your HTML: <div class="loader-container" style="display: none;"></div>
 */
async function waitForAngular(page) {
    try {
        // Wait for spinner to be hidden
        await page.waitForSelector('.loader-container', { hidden: true, timeout: 5000 });
    } catch (e) {
        // If timeout, it means spinner didn't appear or is stuck. We proceed anyway.
    }
    // Hard wait to let the grid repaint (SPA rendering)
    await new Promise(r => setTimeout(r, 2000));
}

/**
 * Handles the TrustArc Cookie Popup.
 * Based on your HTML: <button id="truste-consent-button">Accept All Cookies</button>
 */
async function handleCookies(page) {
    try {
        const btnSelector = '#truste-consent-button';
        const btn = await page.$(btnSelector);

        if (btn) {
            console.log('🍪 TrustArc Cookie Banner detected. Clicking "Accept All"...');
            await btn.click();
            // Wait for the blackbar overlay to go away
            await new Promise(r => setTimeout(r, 3000));
        }
    } catch (e) {
        console.log("   (Cookie banner check skipped or failed)");
    }
}

// ==========================================
// 2. MAIN LOGIC
// ==========================================

async function scrape() {
    console.log("🤖 Launching Scraper V4 (Fixed Scope)...");

    const browser = await puppeteer.launch({
        headless: false, // Visible browser
        defaultViewport: null,
        args: ['--start-maximized']
    });

    const page = await browser.newPage();
    // Set Infinite Timeout (0) because AGCO server is slow
    page.setDefaultNavigationTimeout(0);

    try {
        console.log(`🚀 Navigating to Home: ${BASE_URL}`);
        await page.goto(BASE_URL, { waitUntil: 'domcontentloaded' });

        // Initial setup
        await waitForAngular(page);
        await handleCookies(page);

        // Start recursion
        await scrapeLevel(page, 'Home', 0);

    } catch (err) {
        console.error("❌ CRITICAL ERROR:", err);
    } finally {
        fs.writeFileSync(OUTPUT_FILE, JSON.stringify(fullData, null, 2));
        console.log(`\n✅ DONE! Saved ${fullData.length} items to ${OUTPUT_FILE}`);
        await browser.close();
    }
}

/**
 * Recursive Scraper Function
 */
async function scrapeLevel(page, parentName, depth) {
    const currentUrl = page.url();

    // 1. Safety Checks
    if (depth >= MAX_DEPTH) {
        console.log(`   🛑 Max depth reached (${MAX_DEPTH}). Going back.`);
        return;
    }

    // Cycle Detection (URL + Depth)
    const stateKey = `${currentUrl}::${depth}`;
    if (visitedUrls.has(stateKey)) return;
    visitedUrls.add(stateKey);

    console.log(`\n📂 [Level ${depth}] Scanning: "${parentName}"`);

    // 2. Determine Selector Strategy
    // Based on your HTML: Home uses '.brand-card-group', Inner pages use 'app-cpq-product-card'
    let validSelector = '';

    if (await page.$('.brand-card-group')) {
        validSelector = '.brand-card-group';
    } else if (await page.$('app-cpq-product-card')) {
        validSelector = 'app-cpq-product-card';
    } else if (await page.$('.card')) {
        validSelector = '.card'; // Fallback
    }

    if (!validSelector) {
        console.log("   📝 No cards found. Assuming Leaf/Config Page.");
        return;
    }

    // 3. Collect Items
    // We fetch the count, then loop by index to avoid stale element errors
    const count = await page.$$eval(validSelector, els => els.length);
    console.log(`   Found ${count} items using selector: "${validSelector}"`);

    for (let i = 0; i < count; i++) {
        // REFRESH DOM: Elements die after navigation, we must re-query every loop
        if (i > 0) await waitForAngular(page);

        const cards = await page.$$(validSelector);
        const card = cards[i];

        if (!card) continue;

        // 4. Extract Data
        let data = await page.evaluate((el) => {
            // Your HTML puts titles in <h4 class="card-title"> or img alt tags
            const tEl = el.querySelector('.card-title') || el.querySelector('h4');
            const dEl = el.querySelector('.card-text') || el.querySelector('p');
            const imgEl = el.querySelector('img');

            let title = tEl ? tEl.innerText.trim() : "";
            // Fallback for Home Page Brand Cards
            if (!title && imgEl) title = imgEl.getAttribute('alt');

            return {
                title: title || "Unknown Item",
                desc: dEl ? dEl.innerText.trim() : "",
                img: imgEl ? imgEl.src : ""
            };
        }, card);

        console.log(`   👉 [${i+1}/${count}] Processing: ${data.title}`);

        // Save
        fullData.push({ level: depth, parent: parentName, ...data, url: currentUrl });

        // 5. Drill Down Logic
        // Check if this is a Model Selection (Leaf Node)
        // Your HTML shows checkboxes <div class="chk chk-round"> for models.
        const isLeaf = await card.$('input[type="checkbox"]');

        if (!isLeaf) {
            try {
                // Click the Image (safest click target in Angular cards)
                const clickTarget = await card.$('img') || card;
                await clickTarget.click();

                // Wait for URL change or DOM update
                // Angular SPAs don't always fire 'load', so we wait for the Loader
                await waitForAngular(page);

                // Check if URL actually changed
                if (page.url() === currentUrl) {
                    console.log("      (URL didn't change. Likely a filter/leaf. Skipping recursion.)");
                } else {
                    // RECURSE
                    await scrapeLevel(page, data.title, depth + 1);

                    // GO BACK
                    console.log("      ⬅️ Back...");
                    await page.goBack();
                    await waitForAngular(page);
                }

            } catch (err) {
                console.log(`      ⚠️ Navigation error: ${err.message}`);
            }
        } else {
            console.log("      (Checkbox detected - Model Page. Stopping drill-down.)");
        }
    }
}

scrape();