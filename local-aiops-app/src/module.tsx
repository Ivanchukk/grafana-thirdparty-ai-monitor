import { AppPlugin, PluginExtensionPoints } from '@grafana/data';
import App from './components/App/App';

export const plugin = new AppPlugin<{}>().setRootPage(App).addLink({
  targets: [PluginExtensionPoints.DashboardPanelMenu],
  title: 'Analyze with AI',
  description: 'Investigate this dashboard using live metric evidence',
  path: '/a/local-aiops-app/investigate',
  configure: () => {
    const source = new URLSearchParams(window.location.search);
    const target = new URLSearchParams();
    const dashboard = window.location.pathname.match(/\/d\/([^/]+)/)?.[1];
    if (dashboard) {
      target.set('dashboard', dashboard);
    }
    for (const [key, value] of source.entries()) {
      if (key === 'from' || key === 'to' || key.startsWith('var-')) {
        target.append(key, value);
      }
    }
    return { path: `/a/local-aiops-app/investigate?${target.toString()}` };
  },
});
