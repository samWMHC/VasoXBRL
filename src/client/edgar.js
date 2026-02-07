const BASE_URL = "https://efts.sec.gov/LATEST";
const SUBMISSIONS_URL = "https://data.sec.gov/submissions";
const ARCHIVES_URL = "https://www.sec.gov/Archives/edgar/data";

/**
 * Minimal client for the SEC EDGAR API.
 * SEC requires a User-Agent header identifying the caller.
 * See: https://www.sec.gov/os/accessing-edgar-data
 */
export class EdgarClient {
  constructor({ userAgent }) {
    if (!userAgent) {
      throw new Error(
        "SEC EDGAR requires a User-Agent header (e.g. 'MyApp admin@example.com')"
      );
    }
    this.headers = {
      "User-Agent": userAgent,
      Accept: "application/json",
    };
  }

  async _fetch(url) {
    const res = await fetch(url, { headers: this.headers });
    if (!res.ok) {
      throw new Error(`EDGAR request failed: ${res.status} ${res.statusText}`);
    }
    return res;
  }

  /** Look up a company's CIK by ticker symbol. */
  async cikForTicker(ticker) {
    const res = await this._fetch(
      `${BASE_URL}/search-index?q=%22${encodeURIComponent(ticker)}%22&dateRange=custom&startdt=2024-01-01&forms=10-K`
    );
    const data = await res.json();
    const hit = data.hits?.hits?.[0];
    if (!hit) throw new Error(`No CIK found for ticker "${ticker}"`);
    return hit._source.entity_id.replace("CIK", "").replace(/^0+/, "");
  }

  /** Fetch the submission history for a given CIK (zero-padded to 10 digits). */
  async getSubmissions(cik) {
    const padded = String(cik).padStart(10, "0");
    const res = await this._fetch(`${SUBMISSIONS_URL}/CIK${padded}.json`);
    return res.json();
  }

  /** Find the most recent filing of a given form type (e.g. "10-K", "10-Q"). */
  async getRecentFiling(cik, formType = "10-K") {
    const submissions = await this.getSubmissions(cik);
    const recent = submissions.filings?.recent;
    if (!recent) throw new Error("No recent filings found");

    const idx = recent.form.findIndex((f) => f === formType);
    if (idx === -1) throw new Error(`No ${formType} filing found`);

    return {
      accessionNumber: recent.accessionNumber[idx],
      filingDate: recent.filingDate[idx],
      primaryDocument: recent.primaryDocument[idx],
    };
  }

  /** Download raw filing content by CIK and accession number. */
  async getFilingDocument(cik, accessionNumber, document) {
    const accessionFlat = accessionNumber.replace(/-/g, "");
    const url = `${ARCHIVES_URL}/${cik}/${accessionFlat}/${document}`;
    const res = await this._fetch(url);
    return res.text();
  }
}
