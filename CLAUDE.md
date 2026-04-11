# NASA ADS Skill Repository

This repository is a marketplace repo. The installable Claude plugin lives in `plugins/nasa-ads/`.

## Claude Plugin

- Plugin root: `plugins/nasa-ads/`
- Manifest: `plugins/nasa-ads/.claude-plugin/plugin.json`
- Marketplace: `.claude-plugin/marketplace.json`
- Commands are namespaced by plugin id: `/nasa-ads:ads-search`, `/nasa-ads:ads-bibtex`, `/nasa-ads:ads-library`, `/nasa-ads:ads-metrics`, `/nasa-ads:ads-cite`

## API Token

The ADS API requires a personal token. Check `ADS_API_TOKEN` first, then `ADS_DEV_KEY`. If neither is set, prompt the user.

Token page: https://ui.adsabs.harvard.edu/#user/settings/token
