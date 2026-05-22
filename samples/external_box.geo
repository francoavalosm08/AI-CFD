SetFactory("OpenCASCADE");
Mesh.MshFileVersion = 2.2;
Mesh.CharacteristicLengthMin = 2.0;
Mesh.CharacteristicLengthMax = 3.0;

Box(1) = {-5, -5, -0.5, 15, 10, 1};

inlet[] = Surface In BoundingBox{-5.001, -5.001, -0.501, -4.999, 5.001, 0.501};
outlet[] = Surface In BoundingBox{9.999, -5.001, -0.501, 10.001, 5.001, 0.501};
wall[] = Surface In BoundingBox{-5.001, -5.001, -0.501, 10.001, 5.001, 0.501};
wall[] -= inlet[];
wall[] -= outlet[];

Physical Surface("inlet") = inlet[];
Physical Surface("outlet") = outlet[];
Physical Surface("wall") = wall[];
Physical Volume("internal") = {1};
