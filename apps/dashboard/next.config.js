/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  async redirects() {
    return [
      {
        source: '/routes',
        destination: '/corridors',
        permanent: false,
      },
      {
        source: '/routes/:route_id',
        destination: '/corridors/:route_id',
        permanent: false,
      },
      {
        source: '/carrier-inflation',
        destination: '/market-dynamics?tab=carriers',
        permanent: false,
      },
      {
        source: '/lead-time',
        destination: '/market-dynamics?tab=lead-time',
        permanent: false,
      },
      {
        source: '/fluctuations',
        destination: '/market-dynamics?tab=volatility',
        permanent: false,
      },
      {
        source: '/fuel-context',
        destination: '/market-dynamics?tab=fuel',
        permanent: false,
      },
      {
        source: '/validation',
        destination: '/governance?tab=validation',
        permanent: false,
      },
      {
        source: '/quality',
        destination: '/governance?tab=quality',
        permanent: false,
      },
      {
        source: '/sources',
        destination: '/governance?tab=sources',
        permanent: false,
      },
      {
        source: '/methodology',
        destination: '/governance?tab=methodology',
        permanent: false,
      },
    ];
  },
};

module.exports = nextConfig;
