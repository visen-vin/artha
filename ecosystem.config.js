module.exports = {
  apps: [
    {
      name: 'feed-crypto',
      script: '/root/.local/bin/uv',
      args: 'run python -m artha.bin.feed_crypto',
      autorestart: true,
      watch: false,
      cwd: '/root/artha',
      env: {
        PYTHONPATH: '.',
      },
    },
    {
      name: 'feed-india',
      script: '/root/.local/bin/uv',
      args: 'run python -m artha.bin.feed_india',
      autorestart: true,
      watch: false,
      cwd: '/root/artha',
      env: {
        PYTHONPATH: '.',
      },
    },
    {
      name: 'strategy-host',
      script: '/root/.local/bin/uv',
      args: 'run python -m artha.bin.strategy_host',
      autorestart: true,
      watch: false,
      cwd: '/root/artha',
      env: {
        PYTHONPATH: '.',
      },
    },
    {
      name: 'core-engine',
      script: '/root/.local/bin/uv',
      args: 'run python -m artha.bin.core_engine',
      autorestart: true,
      watch: false,
      cwd: '/root/artha',
      env: {
        PYTHONPATH: '.',
      },
    },
    {
      name: 'control-bot',
      script: '/root/.local/bin/uv',
      args: 'run python -m artha.bin.control_bot',
      autorestart: true,
      watch: false,
      cwd: '/root/artha',
      env: {
        PYTHONPATH: '.',
      },
    },
    {
      name: 'watchdog',
      script: '/root/.local/bin/uv',
      args: 'run python -m artha.bin.watchdog',
      autorestart: true,
      watch: false,
      cwd: '/root/artha',
      env: {
        PYTHONPATH: '.',
      },
    },
  ],
};
