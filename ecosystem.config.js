module.exports = {
  apps: [
    {
      name: 'feed-crypto',
      script: 'artha/bin/feed_crypto.py',
      interpreter: '/root/artha/.venv/bin/python3',
      autorestart: true,
      watch: false,
      cwd: '/root/artha',
      env: {
        PYTHONPATH: '.',
      },
    },
    {
      name: 'feed-india',
      script: 'artha/bin/feed_india.py',
      interpreter: '/root/artha/.venv/bin/python3',
      autorestart: true,
      watch: false,
      cwd: '/root/artha',
      env: {
        PYTHONPATH: '.',
      },
    },
    {
      name: 'strategy-host',
      script: 'artha/bin/strategy_host.py',
      interpreter: '/root/artha/.venv/bin/python3',
      autorestart: true,
      watch: false,
      cwd: '/root/artha',
      env: {
        PYTHONPATH: '.',
      },
    },
    {
      name: 'core-engine',
      script: 'artha/bin/core_engine.py',
      interpreter: '/root/artha/.venv/bin/python3',
      autorestart: true,
      watch: false,
      cwd: '/root/artha',
      env: {
        PYTHONPATH: '.',
      },
    },
    {
      name: 'control-bot',
      script: 'artha/bin/control_bot.py',
      interpreter: '/root/artha/.venv/bin/python3',
      autorestart: true,
      watch: false,
      cwd: '/root/artha',
      env: {
        PYTHONPATH: '.',
      },
    },
    {
      name: 'watchdog',
      script: 'artha/bin/watchdog.py',
      interpreter: '/root/artha/.venv/bin/python3',
      autorestart: true,
      watch: false,
      cwd: '/root/artha',
      env: {
        PYTHONPATH: '.',
      },
    },
  ],
};
