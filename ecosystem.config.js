module.exports = {
  apps: [
    {
      name: 'feed-crypto',
      script: 'python3',
      args: '-m artha.bin.feed_crypto',
      autorestart: true,
      watch: false,
    },
    {
      name: 'feed-india',
      script: 'python3',
      args: '-m artha.bin.feed_india',
      autorestart: true,
      watch: false,
    },
    {
      name: 'strategy-host',
      script: 'python3',
      args: '-m artha.bin.strategy_host',
      autorestart: true,
      watch: false,
    },
    {
      name: 'core-engine',
      script: 'python3',
      args: '-m artha.bin.core_engine',
      autorestart: true,
      watch: false,
    },
    {
      name: 'control-bot',
      script: 'python3',
      args: '-m artha.bin.control_bot',
      autorestart: true,
      watch: false,
    },
    {
      name: 'watchdog',
      script: 'python3',
      args: '-m artha.bin.watchdog',
      autorestart: true,
      watch: false,
    },
  ],
};
