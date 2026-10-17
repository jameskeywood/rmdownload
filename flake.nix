{
  description = "rmdownload: download reMarkable 2 files and convert notebooks to PDF";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs = { self, nixpkgs }:
    let
      system = "x86_64-linux";
      pkgs = import nixpkgs { inherit system; };
    in {
      devShells.${system}.default = pkgs.mkShell {
        packages = with pkgs; [
          uv
          python3
          rsync
          openssh
        ];
      };
    };
}
