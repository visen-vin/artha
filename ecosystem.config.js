module.exports = {
  apps: [
    {
      name: 'feed-crypto',
      script: '/root/.local/bin/uv',
      args: 'run python -m artha.bin.feed_crypto',
      interpreter: 'none',
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
      interpreter: 'none',
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
      interpreter: 'none',
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
      interpreter: 'none',
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
      interpreter: 'none',
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
      interpreter: 'none',
      autorestart: true,
      watch: false,
      cwd: '/root/artha',
      env: {
        PYTHONPATH: '.',
      },
    },
  ],
};
