Name:           nwg-look
Version:        1.1.1
Release:        1%{?dist}
Summary:        GTK3 settings editor for sway and other wlroots compositors
License:        MIT
URL:            https://github.com/nwg-piotr/nwg-look
Source0:        %{url}/archive/v%{version}/nwg-look-%{version}.tar.gz

BuildRequires:  golang >= 1.21
BuildRequires:  gcc
BuildRequires:  gtk3-devel

%description
nwg-look is a GTK3 settings editor designed to work with sway and other
wlroots-based Wayland compositors. It lets you set the GTK theme, icon
theme, cursor theme, and font.

%prep
%autosetup -n nwg-look-%{version}

%build
go build -v -o bin/nwg-look .

%install
make install DESTDIR=%{buildroot} PREFIX=%{_prefix}

%files
%license LICENSE
%doc README.md
%{_bindir}/nwg-look
%{_datadir}/nwg-look/
%{_datadir}/applications/nwg-look.desktop
%{_datadir}/pixmaps/nwg-look.svg
