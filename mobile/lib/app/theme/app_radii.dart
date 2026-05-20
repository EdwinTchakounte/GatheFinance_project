import 'package:flutter/material.dart';

/// Rayons utilisés à travers l'app — proche du langage iOS/Material 3 moderne.
class AppRadii {
  AppRadii._();

  static const r4 = Radius.circular(4);
  static const r8 = Radius.circular(8);
  static const r12 = Radius.circular(12);
  static const r16 = Radius.circular(16);
  static const r20 = Radius.circular(20); // default for cards
  static const r24 = Radius.circular(24);
  static const r28 = Radius.circular(28); // hero cards
  static const pill = Radius.circular(9999);

  static const card = BorderRadius.all(r20);
  static const cardHero = BorderRadius.all(r28);
  static const sheet = BorderRadius.vertical(top: r24);
  static const button = BorderRadius.all(pill);
  static const chip = BorderRadius.all(pill);
  static const field = BorderRadius.all(r12);
}
