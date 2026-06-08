// Vercel serverless function — proxies email signups to Kit (ConvertKit) API
// Keeps the API key server-side, never exposed to the browser.

export default async function handler(req, res) {
  // Only accept POST
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  const { email } = req.body || {};
  if (!email || !email.includes('@')) {
    return res.status(400).json({ error: 'Valid email required' });
  }

  try {
    const response = await fetch('https://api.convertkit.com/v3/forms/9537633/subscribe', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        api_key: process.env.CONVERTKIT_API_KEY,
        email: email,
      }),
    });

    const data = await response.json();

    if (response.ok && data.subscription) {
      return res.status(200).json({ success: true });
    } else {
      return res.status(400).json({ error: data.error || 'Subscription failed' });
    }
  } catch (err) {
    return res.status(500).json({ error: 'Server error, please try again' });
  }
}
