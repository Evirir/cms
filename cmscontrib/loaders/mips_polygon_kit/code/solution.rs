use std::io::{self, Read};

fn main() {
    let mut input = String::new();
    io::stdin().read_to_string(&mut input).unwrap();
    // `input` holds the whole input file from standard input. Read it, e.g.
    // let n: i64 = input.trim().parse().unwrap();
    // Print the answer for it to standard output, e.g. println!("{}", n);
}
