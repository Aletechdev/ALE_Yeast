# Setting Up Swap on Azure Linux VM

## Why

The D4as_v5 VM has 16 GB RAM and no swap by default. For memory-intensive steps
(e.g., GATK joint calling with 86+ GVCFs), adding swap prevents OOM kills by
spilling to disk instead of crashing.

## Setup (8 GB swap file on OS disk)

```bash
sudo fallocate -l 8G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

Verify:
```bash
swapon --show
free -h
```

## What happens

- Linux only uses swap when RAM is nearly full (default swappiness=60)
- Swap on SSD is ~100x slower than RAM, but processes survive instead of OOM-killing
- Disk impact: -8 GB from free space (negligible on 1 TB OS disk)
- Persistent across reboots (via fstab entry)

## Undo

```bash
sudo swapoff /swapfile
sudo rm /swapfile
sudo sed -i '/\/swapfile/d' /etc/fstab
```

## Notes

- This VM has a single 1 TB OS disk (`/dev/sda`, ext4) — no ephemeral/temp disk
- `fallocate` works on ext4; use `dd` instead on XFS or btrfs
- For VMs with an ephemeral disk (`/mnt`), prefer swap there for lower latency
  (but data is wiped on deallocation)
