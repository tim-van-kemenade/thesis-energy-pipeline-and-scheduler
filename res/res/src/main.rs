use clap::Parser;
use std::thread;

/// Simple program to greet a person
#[derive(Parser, Debug)]
#[command(version, about, long_about = None)]
struct Args {
    /// Number of cpu's to block
    #[arg(short, long, default_value_t = 1)]
    num_cpu: u8,
}

fn block_cpu() {
    let mut dummy = 1;
    while dummy < 10_000 {
        dummy += 1;
        if dummy > 1000 {
            dummy = 0;
        }
    }
}

fn main() {
    let args = Args::parse();

    let mut handles = Vec::new();
    for _ in 0..args.num_cpu {
        let handle = thread::spawn(move || block_cpu());
        handles.push(handle);
    }

    for handle in handles {
        let _ = handle.join();
    }
}
